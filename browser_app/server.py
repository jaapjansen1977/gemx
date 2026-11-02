"""Local-only web UI. Start with python -m browser_app.server."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid
from zipfile import ZipFile, ZIP_DEFLATED

import numpy as np
from flask import Flask, abort, jsonify, render_template, request, send_file, session

def resource_root():
    # A frozen entry script lives directly in _MEIPASS, outside its source package.
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))


ROOT = resource_root()
FILES = {'csv': 'review/angles.csv', 'qpos': 'review/qpos.csv', 'plot': 'review/angles.png',
         'report': 'review/report.json', 'arrays': 'review/model-coordinates.npz',
         'motion': 'fit/fit.npz', 'video': 'fit/preview.mp4', 'validation': 'review/validation.json',
         'zip': 'resultaten.zip', 'log': 'engine.log'}


@dataclass
class Job:
    id: str
    directory: Path
    kind: str
    status: str = 'queued'
    message: str = 'Analyse wordt gestart'
    log: list = field(default_factory=list)
    process: object = None
    cancel: threading.Event = field(default_factory=threading.Event)


class Jobs:
    def __init__(self, directory, engine=None):
        self.directory = Path(directory).resolve()
        self.engine = engine or {}
        self.items = {}
        self.lock = threading.Lock()
        # Matplotlib and the CPU inference engine run one task at a time.
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='gemx-web')

    def create(self, kind):
        with self.lock:
            if any(j.status in ('queued', 'running') for j in self.items.values()):
                raise RuntimeError('Er loopt al een analyse. Wacht tot die klaar is.')
            key = uuid.uuid4().hex
            directory = self.directory / key
            directory.mkdir(parents=True, exist_ok=False)
            job = Job(key, directory, kind)
            self.items[key] = job
            return job

    def update(self, job, message):
        with self.lock:
            job.message = message
            job.log.append(message)
            job.log[:] = job.log[-120:]

    def run(self, job, settings):
        job.status = 'running'
        try:
            if job.kind == 'demo':
                from myo_fit.export_results import export
                self.update(job, 'Opgeslagen MyoFullBody-modelfit opnieuw controleren en modelcoordinaten exporteren')
                (job.directory/'fit').mkdir()
                for filename in ('fit.npz','report.json','preview.mp4'):
                    shutil.copyfile(ROOT/'myo_fit/results'/filename, job.directory/'fit'/filename)
                export(job.directory/'fit/fit.npz',job.directory/'review',job.directory/'fit/report.json')
            else:
                self.update(job, 'Video lokaal verwerken met de ingestelde GEM-X-motor')
                req = {**settings, 'output': str(job.directory), 'config': str(self.engine['config']),
                       'assets': str(self.engine['assets']), 'threads': 2}
                path = job.directory/'request.json'
                path.write_text(json.dumps(req, indent=2), encoding='utf-8')
                env = os.environ.copy()
                env['PYTHONPATH'] = str(ROOT/'engine_source' if getattr(sys, 'frozen', False) else ROOT)
                with (job.directory/'engine.log').open('w', encoding='utf-8') as log:
                    if sys.platform == 'win32' and getattr(sys, 'frozen', False):
                        import ctypes
                        dll_directory = ctypes.windll.kernel32.SetDllDirectoryW
                        dll_directory.argtypes = [ctypes.c_wchar_p]
                        dll_directory(None)
                    try:
                        process = subprocess.Popen([str(self.engine['python']), '-u', '-m', 'desktop_app.engine', str(path)],
                            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding='utf-8', errors='replace',
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    finally:
                        if sys.platform == 'win32' and getattr(sys, 'frozen', False): dll_directory(str(ROOT))
                    job.process = process
                    if job.cancel.is_set(): process.terminate()
                    for line in process.stdout:
                        log.write(line); log.flush(); self.update(job, line.rstrip())
                    code = process.wait()
                if job.cancel.is_set():
                    job.status = 'cancelled'; self.update(job, 'Analyse gestopt'); return
                if code != 0 or not (job.directory/'completed.json').exists():
                    raise RuntimeError('De videomotor kon de analyse niet afronden. Download het logboek voor de foutmelding.')
            if job.cancel.is_set():
                job.status = 'cancelled'; self.update(job, 'Analyse gestopt'); return
            self.finish(job)
            self.update(job, 'Klaar. De 3D-beweging, hoeken en downloads staan hieronder.')
            job.status = 'completed'
        except Exception as error:
            import traceback
            traceback.print_exc()
            self.update(job, str(error))
            job.status = 'failed'
        finally:
            job.process = None

    def finish(self, job):
        report=json.loads((job.directory/'review/report.json').read_text(encoding='utf-8'))
        if report.get('source')!='mujoco_myofullbody_fit' or report['validation']['status']!='passed':
            raise ValueError('Resultaat is geen gecontroleerde MyoFullBody-modelfit')
        with ZipFile(job.directory/'resultaten.zip', 'w', ZIP_DEFLATED) as archive:
            for key, name in FILES.items():
                path = job.directory/name
                if key not in ('zip', 'log') and path.is_file(): archive.write(path, name)

    def close(self):
        for job in self.items.values():
            job.cancel.set()
            if job.process is not None and job.process.poll() is None: job.process.terminate()
        self.executor.shutdown(wait=True, cancel_futures=True)


def number(value, default, low, high):
    try: result = float(default if value is None else value)
    except (TypeError, ValueError): raise ValueError('Vul geldige tijden in seconden in.')
    if not math.isfinite(result) or not low < result <= high:
        raise ValueError(f'De tijd moet groter dan {low:g} en maximaal {high:g} seconden zijn.')
    return result


def json_values(array):
    # Strict JSON: NaN becomes null, preserving gaps in singular YXY intervals.
    array = np.asarray(array)
    return np.where(np.isfinite(array), array, None).tolist()


def create_app(directory=None, engine=None):
    app = Flask(__name__, template_folder=str(ROOT/'browser_app/templates'),
                static_folder=str(ROOT/'browser_app/static'), static_url_path='/static')
    app.config.update(SECRET_KEY=secrets.token_hex(32), MAX_CONTENT_LENGTH=256*1024*1024,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
                      TRUSTED_HOSTS=['localhost', '127.0.0.1'])
    jobs = Jobs(directory or ROOT/'outputs/browser-app', engine)
    app.extensions['jobs'] = jobs

    @app.before_request
    def protect():
        if request.path.startswith('/api/'):
            token = session.get('csrf')
            if not token: abort(403)
            if request.method == 'POST':
                if not secrets.compare_digest(request.headers.get('X-GEMX-Token', ''), token): abort(403)
                origin = request.headers.get('Origin')
                if origin and origin != request.host_url.rstrip('/'): abort(403)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        if request.path.startswith('/api/'): response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(413)
    def too_large(error): return jsonify(error='De video is te groot. Kies een bestand kleiner dan 256 MB.'), 413

    @app.get('/')
    def home():
        session.setdefault('csrf', secrets.token_hex(32))
        return render_template('index.html', csrf=session['csrf'], video_ready=bool(jobs.engine))

    @app.get('/plotly.js')
    def plotly_script():
        from plotly.offline import get_plotlyjs
        return app.response_class(get_plotlyjs(), mimetype='application/javascript')

    def find(key):
        job = jobs.items.get(key)
        if job is None: abort(404)
        return job

    def start_job(kind):
        if kind == 'video' and not jobs.engine:
            return jsonify(error='Eigen videoanalyse is nog niet ingesteld op deze computer. De proefclip is wel beschikbaar.'), 503
        try:
            values = request.get_json(silent=True) or {} if kind == 'demo' else request.form
            if not hasattr(values, 'get'): raise ValueError('Ongeldige analyse-instellingen.')
            duration = 2.0 if kind == 'demo' else number(values.get('duration'), 2, 0, 60)
            if 'neutral_seconds' in values: raise ValueError('Extra nulcorrectie is niet beschikbaar voor de MuJoCo-modelfit.')
            settings = dict(duration=duration)
            if kind == 'video':
                settings['start'] = number(values.get('start'), 0, -1e-12, 1e9)
                upload = request.files.get('video')
                if upload is None or not upload.filename: raise ValueError('Kies eerst een video.')
                suffix = Path(upload.filename).suffix.lower()
                if suffix not in ('.mp4', '.mov', '.avi', '.mkv'): raise ValueError('Kies een MP4-, MOV-, AVI- of MKV-bestand.')
            job = jobs.create(kind)
            if kind == 'video':
                try:
                    target = job.directory/('input'+suffix)
                    upload.save(target)
                    settings['video'] = str(target)
                except Exception:
                    job.status = 'failed'; raise
            jobs.executor.submit(jobs.run, job, settings)
            return jsonify(id=job.id), 202
        except ValueError as error: return jsonify(error=str(error)), 400
        except RuntimeError as error: return jsonify(error=str(error)), 409

    @app.post('/api/jobs/demo')
    def demo(): return start_job('demo')

    @app.post('/api/jobs/video')
    def video(): return start_job('video')

    @app.get('/api/jobs/<key>')
    def status(key):
        job = find(key)
        with jobs.lock: return jsonify(id=job.id, status=job.status, message=job.message, log=list(job.log))

    @app.post('/api/jobs/<key>/cancel')
    def cancel(key):
        job = find(key); job.cancel.set()
        if job.process is not None and job.process.poll() is None: job.process.terminate()
        return jsonify(status='stop_requested')

    @app.get('/api/jobs/<key>/data')
    def data(key):
        job = find(key)
        if job.status != 'completed': return jsonify(error='De analyse is nog niet voltooid.'), 409
        with np.load(job.directory/'review/model-coordinates.npz', allow_pickle=False) as source:
            values={name:source[name].copy() for name in source.files}
        report=json.loads((job.directory/'review/report.json').read_text(encoding='utf-8'))
        parents=values['body_parents'].copy();parents[parents==0]=-1
        return jsonify(source=report['source'],times=values['times_s'].tolist(),names=values['body_names'].tolist(),
                       parents=parents.tolist(),positions=values['body_positions_m'].tolist(),
                       coordinates=report['coordinates'],values=json_values(values['values']),
                       report=report,validation=report['validation'])

    @app.get('/api/jobs/<key>/files/<name>')
    def download(key, name):
        job = find(key)
        if name not in FILES: abort(404)
        if name != 'log' and job.status != 'completed': abort(409)
        path = job.directory/FILES[name]
        if not path.is_file(): abort(404)
        return send_file(path, as_attachment=name not in ('plot','video'), download_name=path.name)

    return app



def self_test(directory):
    app = create_app(directory)
    try:
        client = app.test_client()
        page = client.get('/')
        if page.status_code != 200 or b'Beweging in 3D' not in page.data:
            raise RuntimeError('Browser template missing')
        if client.get('/static/app.js').status_code != 200:
            raise RuntimeError('Browser JavaScript missing')
        with client.session_transaction() as values: token = values['csrf']
        response = client.post('/api/jobs/demo', json={}, headers={'X-GEMX-Token': token})
        if response.status_code != 202: raise RuntimeError(response.get_data(as_text=True))
        key = response.json['id']
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            status = client.get('/api/jobs/'+key).json
            if status['status'] in ('completed', 'failed'): break
            time.sleep(.05)
        if status['status'] != 'completed': raise RuntimeError(str(status))
        data = client.get('/api/jobs/'+key+'/data').json
        check = data['validation']
        if check['status'] != 'passed' or check['frames'] != 60:
            raise RuntimeError('MuJoCo validation failed')
        with client.get('/api/jobs/'+key+'/files/zip') as download:
            if download.status_code != 200 or not download.data: raise RuntimeError('Download failed')
        result = dict(status='passed', source=data['source'],frames=check['frames'], joints=check['joints'],scalar_coordinates=check['scalar_coordinates'],
                      template=True, javascript=True, angle_export=True, zip_download=True)
        (Path(directory)/'browser-self-test.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result, indent=2))
    finally: app.extensions['jobs'].close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', type=Path)
    parser.add_argument('--open-browser', action='store_true')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data-dir', type=Path, default=Path.home()/'GEMX-resultaten/browser')
    parser.add_argument('--engine-python', type=Path)
    parser.add_argument('--engine-config', type=Path)
    parser.add_argument('--soma-assets', type=Path)
    args = parser.parse_args()
    if args.self_test:
        self_test(args.self_test)
        return
    values = (args.engine_python, args.engine_config, args.soma_assets)
    if any(values) and not all(values): parser.error('Stel alle drie de videomotorpaden in, of laat ze alle drie weg.')
    if all(values) and not (values[0].is_file() and values[1].is_file() and values[2].is_dir()):
        parser.error('Controleer de Python-, configuratie- en assetpaden van de videomotor.')
    engine = dict(python=values[0].resolve(), config=values[1].resolve(), assets=values[2].resolve()) if all(values) else None
    app = create_app(args.data_dir, engine)
    print(f'Open http://127.0.0.1:{args.port} in je browser. Stop met Ctrl+C.', flush=True)
    if args.open_browser or getattr(sys, 'frozen', False):
        import webbrowser
        threading.Timer(1, lambda: webbrowser.open(f'http://127.0.0.1:{args.port}')).start()
    try: app.run(host='127.0.0.1', port=args.port, debug=False, threaded=True, use_reloader=False)
    finally: app.extensions['jobs'].close()


if __name__ == '__main__': main()

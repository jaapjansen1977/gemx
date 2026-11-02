"""Tk desktop shell; inference runs in a separate configured Python process."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog,messagebox,ttk


def resources():
    return Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))


def open_file(path):
    if sys.platform=='win32':os.startfile(str(path))
    else:subprocess.Popen(['xdg-open',str(path)])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--play',type=Path);parser.add_argument('--self-test',type=Path);args=parser.parse_args()
    if args.self_test:
        from myo_fit.export_results import export
        report=export(resources()/'myo_fit/results/fit.npz',args.self_test,resources()/'myo_fit/results/report.json')
        (args.self_test/'desktop-self-test.json').write_text(json.dumps(report['validation'],indent=2),encoding='utf-8')
        return
    if args.play:
        from myo_fit.view import main as play_model
        sys.argv=['myo_fit.view','--fit',str(args.play)]
        play_model();return
    root=tk.Tk();root.title('GEM-X Bewegingsanalyse - experimenteel');root.geometry('850x700')
    frame=ttk.Frame(root,padding=20);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='GEM-X Bewegingsanalyse',font=('Segoe UI',19,'bold')).pack(anchor='w')
    ttk.Label(frame,text='MyoFullBody-modelfit / MuJoCo-weergave / Modelcoordinaten',font=('Segoe UI',11)).pack(anchor='w',pady=(3,14))
    ttk.Label(frame,text='Bron: gefitte MuJoCo-qpos. Alle 122 modelcoordinaten in CSV; geen extra nulcorrectie of ISB-validatie.',wraplength=790).pack(anchor='w')
    video=tk.StringVar();destination=tk.StringVar(value=str(Path.home()/'GEMX-resultaten'));start=tk.StringVar(value='0');duration=tk.StringVar(value='2')
    runtime=tk.StringVar();config=tk.StringVar();assets=tk.StringVar();state={'process':None,'busy':False,'result':None}
    def row(parent,label,var,folder=False,filetypes=None):
        bar=ttk.Frame(parent);bar.pack(fill='x',pady=4);ttk.Label(bar,text=label,width=23).pack(side='left')
        ttk.Entry(bar,textvariable=var).pack(side='left',fill='x',expand=True)
        def browse():
            value=filedialog.askdirectory() if folder else filedialog.askopenfilename(filetypes=filetypes or [('Alle bestanden','*.*')])
            if value:var.set(value)
        ttk.Button(bar,text='Kiezen...',command=browse).pack(side='right',padx=(6,0))
    row(frame,'Video',video,filetypes=[('Video','*.mp4 *.mov *.avi *.mkv'),('Alle bestanden','*.*')]);row(frame,'Resultaten opslaan in',destination,folder=True)
    opts=ttk.Frame(frame);opts.pack(fill='x',pady=8)
    for label,var in [('Start (s)',start),('Lengte (s, maximaal 60)',duration)]:
        ttk.Label(opts,text=label).pack(side='left',padx=(0,5));ttk.Entry(opts,textvariable=var,width=7).pack(side='left',padx=(0,12))
    settings=ttk.LabelFrame(frame,text='Videomotor - eenmalig instellen',padding=8);settings.pack(fill='x',pady=8)
    row(settings,'Python van videomotor',runtime,filetypes=[('Python','python.exe'),('Alle bestanden','*.*')]);row(settings,'GEM-X configuratie',config);row(settings,'SOMA-assetsmap',assets,folder=True)
    ttk.Label(settings,text='Eigen video vraagt de apart geïnstalleerde GEM-X-CPU-motor en officiële lokale modellen. De proefclip werkt zonder die installatie.',wraplength=760).pack(anchor='w')
    settings_path=Path(os.environ.get('APPDATA',str(Path.home()/'.config')))/'GEMXDesktop/settings.json'
    preferences={'runtime':runtime,'config':config,'assets':assets,'destination':destination}
    try:
        saved=json.loads(settings_path.read_text(encoding='utf-8'))
        for key,var in preferences.items():
            if isinstance(saved.get(key),str):var.set(saved[key])
    except (OSError,ValueError):pass
    status=tk.StringVar(value='Gereed. Begin eventueel met de bestaande proefclip.')
    ttk.Label(frame,textvariable=status,wraplength=780).pack(anchor='w',pady=8)
    actions=ttk.Frame(frame);actions.pack(fill='x');log=tk.Text(frame,height=13,wrap='word');log.pack(fill='both',expand=True,pady=10)
    def append(text):
        if root.winfo_exists():log.insert('end',text+'\n');log.see('end')
    def job(action):
        if state['busy']:return
        state['busy']=True
        def worker():
            try:action()
            except Exception as e:root.after(0,lambda e=e:messagebox.showerror('Analyse niet voltooid',str(e)));root.after(0,status.set,'Niet voltooid; bekijk het logboek.')
            finally:state['busy']=False;state['process']=None
        threading.Thread(target=worker,daemon=True).start()
    def folder():
        parent=Path(destination.get()).expanduser();parent.mkdir(parents=True,exist_ok=True)
        target=parent/time.strftime('%Y%m%d-%H%M%S');target.mkdir(exist_ok=False);return target
    def sample():
        target=folder();root.after(0,status.set,'Proefclip analyseren...')
        from myo_fit.export_results import export
        import shutil
        (target/'fit').mkdir()
        shutil.copyfile(resources()/'myo_fit/results/fit.npz',target/'fit/fit.npz')
        shutil.copyfile(resources()/'myo_fit/results/report.json',target/'fit/report.json')
        export(target/'fit/fit.npz',target/'review',target/'fit/report.json')
        state['result']=target;root.after(0,status.set,'Proefclip klaar. Open MuJoCo, de hoekgrafiek of de resultatenmap.')
    def process():
        if not Path(video.get()).is_file():raise ValueError('Kies een bestaande video.')
        for value,label in [(runtime.get(),'Python van de videomotor'),(config.get(),'GEM-X-configuratie')]:
            if not value or not Path(value).is_file():raise ValueError('Stel eerst '+label+' in.')
        if not assets.get() or not Path(assets.get()).is_dir():raise ValueError('Kies de SOMA-assetsmap.')
        s,d=float(start.get()),float(duration.get())
        if not 0<=s or not 0<d<=60 :raise ValueError('Gebruik start >= 0, lengte 0-60 s.')
        target=folder();req=dict(video=str(Path(video.get()).resolve()),config=config.get(),assets=assets.get(),output=str(target),start=s,duration=d,threads=2)
        request=target/'request.json';request.write_text(json.dumps(req,indent=2),encoding='utf-8')
        env=os.environ.copy();env['PYTHONPATH']=str(resources()/'engine_source') if getattr(sys,'frozen',False) else str(resources())
        root.after(0,status.set,'Video wordt verwerkt; CPU-analyse kan lang duren. Voortgang staat hieronder.')
        with (target/'engine.log').open('w',encoding='utf-8') as stream:
            if sys.platform=='win32' and getattr(sys,'frozen',False):
                import ctypes
                dll_directory=ctypes.windll.kernel32.SetDllDirectoryW
                dll_directory.argtypes=[ctypes.c_wchar_p]
                dll_directory(None)
            try:
                p=subprocess.Popen([runtime.get(),'-u','-m','desktop_app.engine',str(request)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=env,cwd=str(resources()),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            finally:
                if sys.platform=='win32' and getattr(sys,'frozen',False):dll_directory(str(resources()))
            state['process']=p
            for line in p.stdout:stream.write(line);stream.flush();root.after(0,append,line.rstrip())
            if p.wait()!=0:raise RuntimeError('Videomotor gestopt. Het logboek staat in '+str(target/'engine.log'))
        if not (target/'completed.json').exists():raise RuntimeError('Videomotor gaf geen voltooiingsbewijs.')
        state['result']=target;root.after(0,status.set,'Analyse klaar. Open MuJoCo, de hoekgrafiek of de resultatenmap.')
    def result(kind):
        target=state['result']
        if not target:messagebox.showinfo('Nog geen resultaat','Voer eerst de proefclip of een videoanalyse uit.');return
        if kind=='play':
            command=[sys.executable,'--play',str(target/'fit/fit.npz')] if getattr(sys,'frozen',False) else [sys.executable,'-m','desktop_app.app','--play',str(target/'fit/fit.npz')]
            subprocess.Popen(command,cwd=str(resources()))
        else:open_file(target/'review/angles.png' if kind=='plot' else target)
    ttk.Button(actions,text='Bestaande proefclip',command=lambda:job(sample)).pack(side='left',padx=3)
    ttk.Button(actions,text='Video analyseren',command=lambda:job(process)).pack(side='left',padx=3)
    ttk.Button(actions,text='MuJoCo openen',command=lambda:result('play')).pack(side='left',padx=3)
    ttk.Button(actions,text='Hoekgrafiek',command=lambda:result('plot')).pack(side='left',padx=3)
    ttk.Button(actions,text='Resultatenmap',command=lambda:result('folder')).pack(side='left',padx=3)
    def close():
        p=state['process']
        if state['busy'] and not messagebox.askyesno('Afsluiten','Er loopt een analyse. Stoppen en afsluiten?'):return
        if p and p.poll() is None:p.terminate()
        try:
            settings_path.parent.mkdir(parents=True,exist_ok=True)
            settings_path.write_text(json.dumps({k:v.get() for k,v in preferences.items()},indent=2),encoding='utf-8')
        except OSError:pass
        root.destroy()
    root.protocol('WM_DELETE_WINDOW',close);root.mainloop()


if __name__=='__main__':main()

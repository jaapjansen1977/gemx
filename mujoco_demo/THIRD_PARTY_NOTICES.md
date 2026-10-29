# Afhankelijkheden van de MuJoCo-demo

De demo importeert onderstaande pakketten, die tijdens installatie van hun
officiële distributies worden verkregen. Hun licenties zijn van toepassing;
deze notitie herlicentieert geen afhankelijkheden. Binaries worden niet in deze
repository opgenomen.

- MuJoCo 3.3.7: Apache License 2.0. Copyright Google DeepMind en de vermelde
  rechthebbenden. [Licentie](https://github.com/google-deepmind/mujoco/blob/3.3.7/LICENSE)
  en [third-party notices](https://github.com/google-deepmind/mujoco/blob/3.3.7/LICENSES_THIRD_PARTY.md).
- NumPy: BSD-3-Clause en de aanvullende licenties van de gekozen wheel.
  [Licentie](https://github.com/numpy/numpy/blob/main/LICENSE.txt).
- Python GLFW-binding en GLFW: eigen meegeleverde notices;
  [binding](https://github.com/FlorianRhiem/pyGLFW), [GLFW zlib/libpng-licentie](https://www.glfw.org/license.html).
- PyOpenGL: BSD-achtige licentie; zie de officiële wheel en
  [projectlicentie](https://github.com/mcfletch/pyopengl/blob/master/license.txt).
- Transitive Python-afhankelijkheden van MuJoCo, waaronder absl-py en etils:
  hun meegeleverde licenties/notices blijven gelden.
- Optionele video-export: de gekozen FFmpeg-build bepaalt de toepasselijke
  LGPL/GPL- en codecvoorwaarden. De geteste Linux-build bevat libx264 en GPL.
  Lokaal renderen is geen distributie van die binary. Controleer de exacte build
  voordat je een FFmpeg-binary zou bundelen.

Voor de GEM-X-uitvoer en onderzoekscontext: zie `../probe/LICENSE-REVIEW.md`.

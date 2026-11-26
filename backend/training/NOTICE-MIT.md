# Aviso de licencia MIT

`backend/src/recommendation/engine.py` y `backend/training/train.py` adaptan el método de
https://github.com/imaakro/soundpass-recomendador-kmeans (`src/preprocessing.py`, `src/predict.py`):
cuatro señales musicales, controles de 0 a 1, PCA de dos componentes, K-means y orden «mismo perfil
primero, luego distancia». No se reutilizan sus CSV de canciones ni de conciertos, ni sus modelos `.pkl`.

MIT License

Copyright (c) 2026 Camilo Montenegro, Esteban Parra

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

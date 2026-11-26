# Entrenamiento del recomendador (offline)

- `artist_profiles.json`: fuente única de los perfiles de artista (131 artistas, 127 con vector). IDs estables `art_*`, 4 señales de 0 a 1 (bailable, energía, acústico, ánimo), géneros curados e IDs de Ticketmaster observados. **Procedencia:** estimaciones editoriales del proyecto (borrador asistido por IA, pendiente de revisión humana). No salen de Spotify ni de datasets de terceros ni de mediciones de audio.
- `taste_profiles.json`: perfiles de gusto de prueba para el Top 5 e instantánea del catálogo real usada para medir cobertura.
- `train.py`: entrena y evalúa. Escribe `src/recommendation/artifacts/{model,artist_profiles,manifest}.json` y `metrics_report.json`. Es determinista: dos ejecuciones producen los mismos bytes.
- `tests/test_training.py`: pruebas del entrenamiento (requieren numpy y scikit-learn).

```powershell
docker run --rm -v "${PWD}/backend:/work" -w /work python:3.13-slim sh -c "pip install -q -r training/requirements-train.txt && python -m training.train && python tests/test_training.py"
```

El usuario final nunca dispara entrenamiento. El servidor solo lee los artefactos, verifica sus hashes SHA-256 contra `manifest.json` y usa Python puro (sin numpy/scikit-learn ni pickle).

Los centroides, la normalización y el PCA viajan juntos en `model.json`, cuyo `profiles_sha256` ata el modelo a la versión exacta de los perfiles.

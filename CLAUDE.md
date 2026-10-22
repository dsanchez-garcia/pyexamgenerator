# CLAUDE.md

Las instrucciones del proyecto para agentes están en `AGENTS.md` (fuente única, compartida con otros
agentes de IA). Se importan aquí:

@AGENTS.md

## Notas específicas para Claude Code

- Responde al usuario en español salvo que escriba en otro idioma.
- En este equipo el shell por defecto es PowerShell en Windows; para scripts POSIX usa la
  herramienta Bash (Git Bash). El intérprete del proyecto es `venv/Scripts/python.exe`.
- Para tareas de `TODO.md`, trabaja en una rama (o worktree) por tarea y no hagas `git push` ni
  publiques en PyPI sin que el usuario lo pida.
- Si un cambio afecta a la GUI y no puedes verlo funcionando, dilo explícitamente al terminar.

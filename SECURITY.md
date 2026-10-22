# Política de seguridad

## Versiones con soporte

Los problemas de seguridad se corrigen en la última versión publicada en PyPI y en la rama
`master`.

| Versión | Soporte |
|---|---|
| 0.3.x (última publicada) | Sí |
| Anteriores a 0.3 | No |

## Cómo informar de una vulnerabilidad

**No abras un *issue* público** para un problema de seguridad: cualquiera podría aprovecharlo antes
de que se corrija.

1. Usa el aviso privado de GitHub: pestaña **Security → Report a vulnerability** del repositorio.
2. Si esa opción no aparece, escribe al autor a la dirección de contacto que figura en la página del
   paquete en PyPI.

Indica la versión, el sistema operativo, los pasos para reproducirlo y qué impacto tiene. Si
necesitas un ejemplo, crea ficheros pequeños con datos inventados: **nunca envíes datos reales de
alumnos ni tu clave de API**.

El proyecto lo mantiene una sola persona: la respuesta puede tardar unos días. Cuando el problema
esté corregido, se publicará una versión nueva y se describirá en `CHANGELOG.md`.

## Datos personales de alumnos

pyexamgenerator trabaja con datos personales protegidos por el RGPD: nombres, DNI/NIE, correos,
notas y escaneos de hojas de respuestas.

- **La corrección se hace en tu equipo.** Los módulos de corrección (`pyexamgenerator.grading`) no
  envían datos a ningún servicio externo.
- **La generación de preguntas sí usa un servicio externo:** los PDF o imágenes del temario que
  elijas se envían a la API de Google Gemini. No incluyas datos de alumnos en esos ficheros.
- **No subas ficheros reales** al repositorio, a *issues*, *pull requests* ni discusiones (xlsx,
  docx, xml, imágenes de hojas de respuestas). El `.gitignore` los excluye; los tests usan datos
  sintéticos generados en carpetas temporales.
- **Clave de API de Gemini:** el botón «Guardar Clave» la guarda cifrada en el almacén de
  credenciales del sistema (Administrador de credenciales de Windows, Llavero de macOS o Secret
  Service en Linux) y «Borrar Clave» la elimina. Solo si el sistema no tiene almacén (p. ej. un
  servidor Linux) se guarda sin cifrar en la carpeta de configuración del usuario, legible solo por
  él, y la aplicación lo avisa. La variable de entorno `GEMINI_API_KEY`, si existe, tiene prioridad;
  ten en cuenta que se guarda sin cifrar. Las versiones anteriores escribían la clave sin cifrar en
  `config.json`, en la carpeta desde la que se ejecutaba la aplicación: al arrancar se ofrece
  moverla al almacén y borrar ese fichero. No lo compartas ni lo subas.
- **Ficheros temporales:** el OCR copia las imágenes en la carpeta temporal del sistema
  (`pyexamgenerator_temp`) y las borra al terminar; el «Pipeline completo» borra siempre su carpeta
  `_intermedios`, también si hay un error.
- **Sesiones de corrección:** se guardan en JSON y en pickle (`.pkl`). Abrir un `.pkl` puede
  ejecutar código: la aplicación usa el JSON y solo abre un `.pkl` si lo confirmas. Abre únicamente
  sesiones que hayas creado tú.

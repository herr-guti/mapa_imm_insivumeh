# Mapas de la intensidad de Mercalli modificada
Al correr en terminal `generar_mapas_sismo.py` sobre una base SQLite que contenga la información de un sismo y los reportes de los usuarios de la aplicación **HINSIVUMEH - Alerta temprana de terremotos** se generan dos mapas.
- Un mapa que contiene los reportes de los usuarios para la Intensidad de Mercalli Modificada (IMM).
- Un mapa que categoriza las diferencias entre las intensidades reportadas y las intensidades teóricas, en base a la magnitud del sismo, distancia del usuario al epicentro y la IMM reportada.

El modelo elige una recta según IMM observada a partir del umbral $IMM_o = 4.22$, este valor es dado por Worden, C. B., Gerstenberger, M. C., Rhoades, D. A., & Wald, D. J. (2012). Probabilistic Relationships between Ground-Motion Parameters and Modified Mercalli Intensity in California. *Bulletin of the Seismological Society of America*, 102(1), 204-221. <https://doi.org/10.1785/0120110156>, y se hace la composición con el modelo de Ordaz, Jara y Singh descrito en Moncayo Theurer, M., Velasco, G., Rodríguez, J., & Terán, A. (2016). Análisis comparativo entre 13 leyes de atenuación y los registros de un sismo de grado 7.1 en magnitud
Richter ocurrido en Japón. *Ingeniería*, 20(3), 137-146.

Esta aplicación es parte del Trabajo de Fin de Máster para la Maestría en Análisis y Visualización de Datos Masivos de la Universidad Internaciones.

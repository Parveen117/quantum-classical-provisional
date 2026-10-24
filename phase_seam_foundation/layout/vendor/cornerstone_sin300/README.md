# Pinned CORNERSTONE component geometry

These two GDS files and the license are copied unchanged from
[gdsfactory/cspdk commit 3323b17b4d75c852ed2372d7d13239408cca0eb1](https://github.com/gdsfactory/cspdk/tree/3323b17b4d75c852ed2372d7d13239408cca0eb1).

| Local file | Upstream path | Git blob SHA-1 |
| --- | --- | --- |
| mmi2x2.gds | cspdk/sin300/gds/SiN300nm_1550nm_TE_STRIP_2x2_MMI.gds | 59e02ee8d74f09a9360403c5d0fc17eb5ebe7927 |
| heater.gds | cspdk/sin300/gds/Heater.gds | 04472353dac5a63761cb674b4cf31ab5c8bf519c |
| LICENSE | LICENSE | 51d66f670634c36c56a4fcc0e7ef762a2082f79f |

The upstream repository supplies the MIT license reproduced here. Original
component credit remains with CORNERSTONE and the upstream PDK contributors.
The native layout generator imports the named polygon cells and gives those
cells new short names in the generated hierarchy. It does not redistribute
the proprietary foundry pre-DRC macro or the guideline PDF.

The measured performance of a component is not established by its geometry
or hash. Local checks cover the assembled polygon layout only.

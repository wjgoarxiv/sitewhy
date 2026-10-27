# Data sources and attribution

| Path | Source | License |
|---|---|---|
| `seed/moratorium_nation/moratorium_inventory.csv`, `state_legislation.csv`, `README.md` | Moratorium Nation dataset by Michael Bommarito, refreshed 2026-09-23, https://github.com/mjbommar/moratorium-data-2026 | CC-BY-4.0 (data) |
| `geo/eia861_county_utilities.csv` | U.S. Energy Information Administration, Form EIA-861 2025 (Service Territory, Utility Data), https://www.eia.gov/electricity/data/eia861/ , subset for MD/TX/AZ built by `scripts/build_geo.py` | Public domain (U.S. Government work) |
| `geo/cache/` | U.S. Census Geocoder responses, https://geocoding.geo.census.gov/geocoder/ | Public domain |
| `geo/context/` (county, place) | U.S. Census Bureau TIGERweb, tigerWMS_Current MapServer, layer 82 Counties and layer 28 Incorporated Places, https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Current/MapServer | Public domain (U.S. Government work) |
| `geo/context/` (transmission) | Homeland Infrastructure Foundation-Level Data (HIFLD), Electric Power Transmission Lines, https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Electric_Power_Transmission_Lines/FeatureServer/0 | Public domain (U.S. Government work) |
| map basemap (satellite) | Esri World Imagery, https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x} | Esri proprietary; attribution required ("Esri, Maxar, Earthstar Geographics") |
| map basemap (streets) | OpenStreetMap tile layer, https://tile.openstreetmap.org/{z}/{x}/{y}.png | ODbL 1.0; attribution "© OpenStreetMap contributors" |
| map basemap (dark) | Esri Dark Gray Canvas, https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x} | Esri proprietary; attribution "Esri, HERE, Garmin, © OpenStreetMap contributors" |

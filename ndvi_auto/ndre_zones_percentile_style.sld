<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
  xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd"
  xmlns="http://www.opengis.net/sld"
  xmlns:ogc="http://www.opengis.net/ogc"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <NamedLayer>
    <Name>ndre_zones_percentile_style</Name>
    <UserStyle>
      <Title>NDRE Zones Style (Percentile-based)</Title>
      <FeatureTypeStyle>
        <Rule>
          <RasterSymbolizer>
            <Opacity>1.0</Opacity>
            <ColorMap>
              <!-- Zones bazirane na realnim vrednostima iz CSV-a za parcelu 1427/2 -->
              <!-- Min: -0.155, Max: 0.287, većina vrednosti između -0.05 i 0.15 -->
              <!-- Najniži (0-33%): NDRE < 0.0 (negativne i veoma niske vrednosti) -->
              <ColorMapEntry color="#000000" quantity="-0.2" opacity="0" />
              <ColorMapEntry color="#ff0000" quantity="0.0" label="Najniži NDRE (&lt; 0.0)" />
              <!-- Srednji (33-66%): 0.0 <= NDRE < 0.1 (srednje vrednosti) -->
              <ColorMapEntry color="#ffff00" quantity="0.1" label="Srednji NDRE (0.0 - 0.1)" />
              <!-- Najviši (66-100%): NDRE >= 0.1 (visoke vrednosti) -->
              <ColorMapEntry color="#00ff00" quantity="0.3" label="Najviši NDRE (&gt;= 0.1)" />
            </ColorMap>
          </RasterSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>

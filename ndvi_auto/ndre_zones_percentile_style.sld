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
              <!-- NoData / oblak / senka - transparentno -->
              <ColorMapEntry color="#000000" quantity="-1" opacity="0" />
              <!-- Raspon podataka: Min 0.105, Max 0.255 -->
              <!-- Crvena: NDRE &lt; 0.14 (više azota, manje đubrenja) -->
              <ColorMapEntry color="#000000" quantity="0.05" opacity="0" />
              <ColorMapEntry color="#ff0000" quantity="0.14" label="Crvena zona (&lt; 0.14)" />
              <!-- Žuta: 0.14 &lt;= NDRE &lt; 0.19 (standard) -->
              <ColorMapEntry color="#ffff00" quantity="0.19" label="Žuta zona (0.14 - 0.19)" />
              <!-- Zelena: NDRE &gt;= 0.19 (manje azota, više đubrenja) -->
              <ColorMapEntry color="#00ff00" quantity="0.26" label="Zelena zona (&gt;= 0.19)" />
            </ColorMap>
          </RasterSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>

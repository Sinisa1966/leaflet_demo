<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
  xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd"
  xmlns="http://www.opengis.net/sld"
  xmlns:ogc="http://www.opengis.net/ogc"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <NamedLayer>
    <Name>ndre_gradient_style</Name>
    <UserStyle>
      <Title>NDRE Gradient Style (Green variations)</Title>
      <FeatureTypeStyle>
        <Rule>
          <RasterSymbolizer>
            <Opacity>1.0</Opacity>
            <ChannelSelection>
              <GrayChannel>
                <SourceChannelName>1</SourceChannelName>
              </GrayChannel>
            </ChannelSelection>
            <ColorMap>
              <!-- Mapiraj Red kanal (koji ima najveću varijaciju: 133-160) na zelene nijanse -->
              <!-- Najtamnija zelena za najniže Red vrednosti (133) -->
              <ColorMapEntry color="#003200" quantity="130" opacity="0" />
              <ColorMapEntry color="#003200" quantity="133" label="Najtamnija zelena" />
              <ColorMapEntry color="#1e5a1e" quantity="136" />
              <ColorMapEntry color="#3c823c" quantity="140" label="Tamna zelena" />
              <ColorMapEntry color="#5aaa5a" quantity="144" />
              <ColorMapEntry color="#78c878" quantity="147" label="Srednja zelena" />
              <ColorMapEntry color="#90e690" quantity="151" />
              <ColorMapEntry color="#a8f4a8" quantity="154" label="Svetla zelena" />
              <ColorMapEntry color="#b8fcb8" quantity="157" />
              <!-- Najsvetlija zelena za najviše Red vrednosti (160) -->
              <ColorMapEntry color="#c8ffc8" quantity="160" label="Najsvetlija zelena" />
              <ColorMapEntry color="#c8ffc8" quantity="165" opacity="0" />
            </ColorMap>
          </RasterSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>

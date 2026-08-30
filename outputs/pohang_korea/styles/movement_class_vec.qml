<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28.0">
  <renderer-v2 type="categorizedSymbol" attr="class">
    <categories>
      <category value="1" label="Restricted" symbol="1"/>
      <category value="2" label="Severely Restricted" symbol="2"/>
    </categories>
    <symbols>
      <symbol type="fill" name="1" alpha="0.6">
        <layer class="SimpleFill">
          <prop v="no" k="style"/>
          <prop v="0.6" k="width"/>
          <prop v="0,100,0,200" k="color"/>
          <prop v="solid" k="penstyle"/>
        </layer>
        <layer class="LinePatternFill">
          <prop v="45" k="line_angle"/>
          <prop v="50.0" k="line_spacing"/>
          <prop v="1.5" k="line_width"/>
          <prop v="0,120,0,255" k="line_color"/>
        </layer>
      </symbol>
      <symbol type="fill" name="2" alpha="0.65">
        <layer class="SimpleFill">
          <prop v="no" k="style"/>
          <prop v="0.6" k="width"/>
          <prop v="0,80,0,200" k="color"/>
          <prop v="solid" k="penstyle"/>
        </layer>
        <layer class="LinePatternFill">
          <prop v="45" k="line_angle"/>
          <prop v="30.0" k="line_spacing"/>
          <prop v="1.5" k="line_width"/>
          <prop v="0,100,0,255" k="line_color"/>
        </layer>
        <layer class="LinePatternFill">
          <prop v="135" k="line_angle"/>
          <prop v="30.0" k="line_spacing"/>
          <prop v="1.5" k="line_width"/>
          <prop v="0,100,0,255" k="line_color"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>

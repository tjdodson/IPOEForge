<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28.0">
  <renderer-v2 type="categorizedSymbol" attr="class">
    <categories>
      <category value="0" label="Unrestricted" symbol="0"/>
      <category value="1" label="Restricted" symbol="1"/>
      <category value="2" label="Highly Restricted" symbol="2"/>
    </categories>
    <symbols>
      <symbol type="fill" name="0" alpha="0">
        <layer class="SimpleFill">
          <prop v="0" k="style"/>
        </layer>
      </symbol>
      <symbol type="fill" name="1" alpha="0.3">
        <layer class="LinePatternFill">
          <prop v="45" k="line_angle"/>
          <prop v="10.0" k="line_spacing"/>
          <prop v="1.5" k="line_width"/>
          <prop v="gray" k="line_color"/>
        </layer>
      </symbol>
      <symbol type="fill" name="2" alpha="0.4">
        <layer class="LinePatternFill">
          <prop v="45" k="line_angle"/>
          <prop v="10.0" k="line_spacing"/>
          <prop v="1.5" k="line_width"/>
          <prop v="dimgray" k="line_color"/>
        </layer>
        <layer class="LinePatternFill">
          <prop v="135" k="line_angle"/>
          <prop v="10.0" k="line_spacing"/>
          <prop v="1.5" k="line_width"/>
          <prop v="dimgray" k="line_color"/>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>

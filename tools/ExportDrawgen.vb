' ExportDrawgen.vb
' External or document iLogic rule for Autodesk Inventor.
' Writes a .drawgen.json beside the open part or assembly.
' Drop that file into Drawings Generator. The app already stores the
' DWG templates and the BOM column format.
'
' Inventor's API reports length in centimeters and angles in radians.
' This rule converts both to the inch / degree values the sheet uses.
' For the real views, run tools/CreateDrawing.vb instead. That rule
' uses Standard.idw and lets Inventor place the views and dimensions.

Imports System.Text

Sub Main()
    Dim doc As Document = ThisDoc.Document
    Dim fileKind As String = "ipt"
    If doc.DocumentType = DocumentTypeEnum.kAssemblyDocumentObject Then
        fileKind = "iam"
    ElseIf doc.DocumentType <> DocumentTypeEnum.kPartDocumentObject Then
        MessageBox.Show("Open a part (.ipt) or an assembly (.iam) first.", "Drawings Generator")
        Return
    End If

    Dim modelKind As String = "part"
    If fileKind = "iam" Then modelKind = "assembly"

    Dim props As New System.Collections.Generic.Dictionary(Of String, String)
    props("partNumber") = Prop(doc, "Design Tracking Properties", "Part Number")
    props("description") = Prop(doc, "Design Tracking Properties", "Description")
    props("material") = Prop(doc, "Design Tracking Properties", "Material")
    props("rev") = Prop(doc, "Inventor Summary Information", "Revision Number")
    props("designer") = Prop(doc, "Design Tracking Properties", "Designer")
    props("drawnBy") = Prop(doc, "Inventor Summary Information", "Author")
    props("stockNumber") = Prop(doc, "Design Tracking Properties", "Stock Number")
    props("project") = Prop(doc, "Design Tracking Properties", "Project")
    props("thickness") = ""
    props("scale") = "SEE ABOVE"
    props("sheetNumber") = "1"
    props("sheetCount") = "1"

    Dim uom As UnitsOfMeasure = doc.UnitsOfMeasure
    Dim box As Box = doc.ComponentDefinition.RangeBox
    Dim lengthIn As Double = Math.Abs(uom.ConvertUnits(box.MaxPoint.X - box.MinPoint.X, UnitsTypeEnum.kDatabaseLengthUnits, UnitsTypeEnum.kInchLengthUnits))
    Dim heightIn As Double = Math.Abs(uom.ConvertUnits(box.MaxPoint.Y - box.MinPoint.Y, UnitsTypeEnum.kDatabaseLengthUnits, UnitsTypeEnum.kInchLengthUnits))
    Dim widthIn As Double = Math.Abs(uom.ConvertUnits(box.MaxPoint.Z - box.MinPoint.Z, UnitsTypeEnum.kDatabaseLengthUnits, UnitsTypeEnum.kInchLengthUnits))

    Dim bends As New System.Text.StringBuilder()
    Dim bendCount As Integer = 0
    If fileKind = "ipt" Then
        Try
            Dim partDoc As PartDocument = doc
            Dim sm As SheetMetalComponentDefinition = TryCast(partDoc.ComponentDefinition, SheetMetalComponentDefinition)
            If sm IsNot Nothing Then
                modelKind = "part"
                Dim thick As Double = uom.ConvertUnits(sm.Thickness.Value, UnitsTypeEnum.kDatabaseLengthUnits, UnitsTypeEnum.kInchLengthUnits)
                props("thickness") = thick.ToString("0.###")
                If sm.HasFlatPattern Then
                    Dim index As Integer = 1
                    For Each result As FlatBendResult In sm.FlatPattern.FlatBendResults
                        Dim angleDeg As Double = uom.ConvertUnits(result.Angle, UnitsTypeEnum.kDatabaseAngleUnits, UnitsTypeEnum.kDegreeAngleUnits)
                        Dim radiusIn As Double = uom.ConvertUnits(result.InnerRadius, UnitsTypeEnum.kDatabaseLengthUnits, UnitsTypeEnum.kInchLengthUnits)
                        Dim direction As String = "DOWN"
                        If result.IsDirectionUp Then direction = "UP"
                        If bendCount > 0 Then bends.Append(",")
                        bends.Append("{""id"":""" & index.ToString() & """,""direction"":""" & direction & """,""angle"":""" & angleDeg.ToString("0.#") & """,""radius"":""" & radiusIn.ToString("0.###") & """}")
                        bendCount += 1
                        index += 1
                    Next
                End If
            End If
        Catch
        End Try
    End If

    Dim components As New System.Text.StringBuilder()
    If fileKind = "iam" Then
        Try
            Dim asm As AssemblyDocument = doc
            Dim bom As BOM = asm.ComponentDefinition.BOM
            bom.StructuredViewEnabled = True
            bom.StructuredViewFirstLevelOnly = True
            Dim view As BOMView = bom.BOMViews.Item("Structured")
            Dim index As Integer = 0
            For Each row As BOMRow In view.BOMRows
                If row.ComponentDefinitions.Count = 0 Then Continue For
                Dim child As Document = row.ComponentDefinitions.Item(1).Document
                If index > 0 Then components.Append(",")
                Dim qty As String = row.ItemQuantity.ToString()
                components.Append("{""item"":""" & row.ItemNumber & """,""partNumber"":""" & J(Prop(child, "Design Tracking Properties", "Part Number")) & """,""description"":""" & J(Prop(child, "Design Tracking Properties", "Description")) & """,""qty"":""" & J(qty) & """}")
                index += 1
            Next
        Catch ex As Exception
            MessageBox.Show("BOM was not exported: " & ex.Message, "Drawings Generator")
        End Try
    End If

    Dim json As String = "{" &
        """schema"":""drawgen/1""," &
        """fileName"":""" & J(System.IO.Path.GetFileName(doc.FullFileName)) & """," &
        """fileKind"":""" & fileKind & """," &
        """properties"":{" &
            """partNumber"":""" & J(props("partNumber")) & """," &
            """description"":""" & J(props("description")) & """," &
            """material"":""" & J(props("material")) & """," &
            """thickness"":""" & J(props("thickness")) & """," &
            """rev"":""" & J(props("rev")) & """," &
            """designer"":""" & J(props("designer")) & """," &
            """drawnBy"":""" & J(props("drawnBy")) & """," &
            """scale"":""SEE ABOVE""," &
            """sheetNumber"":""1""," &
            """sheetCount"":""1""" &
        "}," &
        """model"":{" &
            """kind"":""" & modelKind & """," &
            """overall"":{""length"":" & lengthIn.ToString("0.###") & ",""width"":" & widthIn.ToString("0.###") & ",""height"":" & heightIn.ToString("0.###") & "}," &
            """bends"":[" & bends.ToString() & "]," &
            """components"":[" & components.ToString() & "]," &
            """views"":{}" &
        "}" &
    "}"

    Dim outPath As String = System.IO.Path.ChangeExtension(doc.FullFileName, ".drawgen.json")
    System.IO.File.WriteAllText(outPath, json, Encoding.UTF8)
    MessageBox.Show("Wrote " & outPath & vbLf & "Bend rows: " & bendCount.ToString(), "Drawings Generator")
End Sub

Function Prop(doc As Document, setName As String, propName As String) As String
    Try
        Return CStr(doc.PropertySets.Item(setName).Item(propName).Value)
    Catch
        Return ""
    End Try
End Function

Function J(value As String) As String
    If value Is Nothing Then Return ""
    Return value.Replace("\", "\\").Replace("""", "\""").Replace(vbCr, " ").Replace(vbLf, " ")
End Function

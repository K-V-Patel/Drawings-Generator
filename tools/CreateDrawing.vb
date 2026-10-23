' CreateDrawing.vb
' iLogic rule. Run it from an open part (.ipt) or assembly (.iam).
'
' Creates a drawing from Standard.idw, so the border, title block, and
' dimension style are the Inventor template. Inventor places the front,
' top, and right views, plus an isometric, and adds overall dimensions.
' An assembly also gets a parts list and item balloons.
'
' The drawing is saved as the part number .idw in the sibling Drawing
' folder when that folder exists, otherwise beside the model. An existing
' file is left alone and a -generated name is used.
'
' It also writes a .drawgen.json of those view curves. Drop that file on
' Drawings Generator when you want the same views in the browser.
' This machine cannot open an .idw. Inventor has to project the model.
'
' iLogic misreads a quote typed inside a string, so every quote is Chr(34).
' It also misreads the circle functions on Math, so circles use SineOf.

Imports System.Text
Imports System.Collections.Generic

Sub Main()
    Dim model As Document = ThisDoc.Document
    If model.DocumentType <> DocumentTypeEnum.kPartDocumentObject AndAlso model.DocumentType <> DocumentTypeEnum.kAssemblyDocumentObject Then
        MessageBox.Show("Open a part (.ipt) or an assembly (.iam), then run this rule.", "Drawings Generator")
        Return
    End If
    If String.IsNullOrEmpty(model.FullFileName) Then
        MessageBox.Show("Save the model first. The drawing is named from its part number.", "Drawings Generator")
        Return
    End If

    Dim templatePath As String = FindTemplate()
    If templatePath = "" Then
        MessageBox.Show("Standard.idw was not found in the Inventor template folder.", "Drawings Generator")
        Return
    End If

    Dim app As Inventor.Application = ThisApplication
    Dim previous As Boolean = app.ScreenUpdating
    app.ScreenUpdating = False
    Dim drawDoc As DrawingDocument = Nothing
    Try
        If model.DocumentType = DocumentTypeEnum.kAssemblyDocumentObject Then
            Dim asm As AssemblyDocument = model
            asm.ComponentDefinition.BOM.StructuredViewEnabled = True
            asm.ComponentDefinition.BOM.StructuredViewFirstLevelOnly = True
        End If

        drawDoc = app.Documents.Add(DocumentTypeEnum.kDrawingDocumentObject, templatePath, True)
        Dim sheet As Sheet = drawDoc.ActiveSheet
        Dim tg As TransientGeometry = app.TransientGeometry
        Dim style As DrawingViewStyleEnum = DrawingViewStyleEnum.kHiddenLineRemovedDrawingViewStyle
        Dim front As DrawingView = sheet.DrawingViews.AddBaseView( _
            model, tg.CreatePoint2d(sheet.Width * 0.38, sheet.Height * 0.42), _
            0.1, ViewOrientationTypeEnum.kFrontViewOrientation, style)
        drawDoc.Update()
        front.Scale = FitScale(sheet, model, front)
        drawDoc.Update()

        Dim views As New Dictionary(Of String, DrawingView)
        views("front") = front
        views("top") = sheet.DrawingViews.AddProjectedView(front, tg.CreatePoint2d(front.Position.X, front.Position.Y + front.Height), style)
        views("side") = sheet.DrawingViews.AddProjectedView(front, tg.CreatePoint2d(front.Position.X + front.Width, front.Position.Y), style)
        views("iso") = sheet.DrawingViews.AddBaseView( _
            model, tg.CreatePoint2d(sheet.Width * 0.75, sheet.Height * 0.68), _
            Math.Max(front.Scale * 0.75, 0.01), ViewOrientationTypeEnum.kIsoTopRightViewOrientation, style)
        drawDoc.Update()
        PositionViews(sheet, views, tg)
        drawDoc.Update()
        ShrinkToSheet(drawDoc, sheet, views, tg)
        NameView(views("front"), "FRONT")
        NameView(views("top"), "TOP")
        NameView(views("side"), "SIDE")
        NameView(views("iso"), "ISOMETRIC")

        TryAddOverall(sheet, views("front"), True, tg)
        TryAddOverall(sheet, views("front"), False, tg)
        TryAddOverall(sheet, views("side"), True, tg)
        TryAddOverall(sheet, views("top"), False, tg)

        If model.DocumentType = DocumentTypeEnum.kAssemblyDocumentObject Then
            TryAddPartsList(sheet, views("front"), tg)
            TryAddBalloons(sheet, model, views("iso"), tg)
        End If
        drawDoc.Update()

        Dim idwPath As String = SaveDrawing(drawDoc, model)
        Dim jsonNote As String = ""
        Try
            jsonNote = WriteCurves(model, views)
        Catch ex As Exception
            jsonNote = "View curves were not written: " & ex.Message
        End Try
        MessageBox.Show("Created " & idwPath & vbLf & jsonNote, "Drawings Generator")
    Catch ex As Exception
        MessageBox.Show("Could not create the drawing: " & ex.Message, "Drawings Generator")
    Finally
        app.ScreenUpdating = previous
    End Try
End Sub

Function FindTemplate() As String
    Dim candidates As New List(Of String)
    Try
        Dim folder As String = ThisApplication.DesignProjectManager.ActiveDesignProject.TemplatesPath
        candidates.Add(System.IO.Path.Combine(folder, "en-US", "Standard.idw"))
        candidates.Add(System.IO.Path.Combine(folder, "Standard.idw"))
    Catch
    End Try
    candidates.Add("C:\Users\Public\Documents\Autodesk\Inventor 2025\Templates\en-US\Standard.idw")
    candidates.Add("C:\Users\Public\Documents\Autodesk\Inventor 2026\Templates\en-US\Standard.idw")
    candidates.Add("C:\Users\Public\Documents\Autodesk\Inventor 2024\Templates\en-US\Standard.idw")
    For Each candidate As String In candidates
        If candidate <> "" AndAlso System.IO.File.Exists(candidate) Then Return candidate
    Next
    Return ""
End Function

Function FitScale(sheet As Sheet, model As Document, front As DrawingView) As Double
    Dim box As Box = model.ComponentDefinition.RangeBox
    Dim sizes As New List(Of Double)
    sizes.Add(Math.Abs(box.MaxPoint.X - box.MinPoint.X))
    sizes.Add(Math.Abs(box.MaxPoint.Y - box.MinPoint.Y))
    sizes.Add(Math.Abs(box.MaxPoint.Z - box.MinPoint.Z))
    sizes.Sort()
    sizes.Reverse()
    Dim usableW As Double = Math.Max(sheet.Width - 10, 8)
    Dim usableH As Double = Math.Max(sheet.Height - 14, 6)
    Dim needW As Double = Math.Max(sizes(0) + sizes(1), front.Width / Math.Max(front.Scale, 0.0001))
    Dim needH As Double = Math.Max(sizes(1) + sizes(2), front.Height / Math.Max(front.Scale, 0.0001))
    Return NiceScale(Math.Min(usableW / Math.Max(needW, 0.1), usableH / Math.Max(needH, 0.1)))
End Function

Function NiceScale(exact As Double) As Double
    Dim choices() As Double = {2, 1, 0.5, 0.25, 0.2, 0.1, 1.0 / 12, 1.0 / 16, 0.05, 1.0 / 20, 1.0 / 24, 1.0 / 30, 1.0 / 32, 0.025, 0.02, 1.0 / 48, 1.0 / 50, 1.0 / 64, 0.01, 0.005}
    If exact <= 0 Then Return 0.01
    For Each choice As Double In choices
        If choice <= exact * 1.001 Then Return choice
    Next
    Return choices(choices.Length - 1)
End Function

Sub PositionViews(sheet As Sheet, views As Dictionary(Of String, DrawingView), tg As TransientGeometry)
    Dim front As DrawingView = views("front")
    Dim top As DrawingView = views("top")
    Dim side As DrawingView = views("side")
    Dim iso As DrawingView = views("iso")
    Dim gap As Double = 2.4
    Dim cx As Double = Math.Min(sheet.Width * 0.34, sheet.Width - side.Width - iso.Width - 8)
    If cx < front.Width / 2 + 2 Then cx = front.Width / 2 + 2
    Dim cy As Double = 8.5 + front.Height / 2
    Dim maxCy As Double = sheet.Height - 2 - top.Height - gap - front.Height / 2
    If cy > maxCy Then cy = Math.Max(maxCy, front.Height / 2 + 2)
    TryMove(front, tg.CreatePoint2d(cx, cy))
    TryMove(top, tg.CreatePoint2d(cx, cy + front.Height / 2 + gap + top.Height / 2))
    TryMove(side, tg.CreatePoint2d(cx + front.Width / 2 + gap + side.Width / 2, cy))
    iso.Scale = Math.Max(front.Scale * 0.8, 0.01)
    TryMove(iso, tg.CreatePoint2d(sheet.Width - 3.5 - iso.Width / 2, sheet.Height * 0.62))
End Sub

Sub TryMove(view As DrawingView, point As Point2d)
    Try
        view.Position = point
    Catch
    End Try
End Sub

Sub ShrinkToSheet(drawDoc As DrawingDocument, sheet As Sheet, views As Dictionary(Of String, DrawingView), tg As TransientGeometry)
    Dim marginL As Double = 1.6
    Dim marginR As Double = sheet.Width - 1.6
    Dim marginB As Double = 1.6
    Dim marginT As Double = sheet.Height - 1.6
    For pass As Integer = 1 To 3
        drawDoc.Update()
        Dim minX As Double = marginR
        Dim minY As Double = marginT
        Dim maxX As Double = marginL
        Dim maxY As Double = marginB
        For Each view As DrawingView In views.Values
            minX = Math.Min(minX, view.Position.X - view.Width / 2)
            maxX = Math.Max(maxX, view.Position.X + view.Width / 2)
            minY = Math.Min(minY, view.Position.Y - view.Height / 2)
            maxY = Math.Max(maxY, view.Position.Y + view.Height / 2)
        Next
        Dim overW As Double = (maxX - minX) / Math.Max(marginR - marginL, 1)
        Dim overH As Double = (maxY - minY) / Math.Max(marginT - marginB, 1)
        Dim factor As Double = Math.Max(overW, overH)
        If factor <= 1.08 Then Exit For
        views("front").Scale = NiceScale(views("front").Scale / factor)
        PositionViews(sheet, views, tg)
    Next
    drawDoc.Update()
End Sub

Sub NameView(view As DrawingView, title As String)
    Try
        view.Name = title
        view.ShowLabel = True
    Catch
    End Try
End Sub

Sub TryAddOverall(sheet As Sheet, view As DrawingView, horizontal As Boolean, tg As TransientGeometry)
    Try
        Dim minCurve As DrawingCurve = Nothing
        Dim maxCurve As DrawingCurve = Nothing
        Dim minValue As Double = 1.0E+30
        Dim maxValue As Double = -1.0E+30
        For Each curve As DrawingCurve In view.DrawingCurves
            Dim probe As Point2d = Nothing
            Try
                probe = curve.MidPoint
            Catch
                probe = Nothing
            End Try
            If probe Is Nothing Then Continue For
            Dim value As Double = probe.X
            If Not horizontal Then value = probe.Y
            If value < minValue Then
                minValue = value
                minCurve = curve
            End If
            If value > maxValue Then
                maxValue = value
                maxCurve = curve
            End If
        Next
        If minCurve Is Nothing OrElse maxCurve Is Nothing OrElse minCurve Is maxCurve Then Return
        Dim textPoint As Point2d
        Dim kind As DimensionTypeEnum
        If horizontal Then
            textPoint = tg.CreatePoint2d((minValue + maxValue) / 2, view.Position.Y - view.Height / 2 - 1.3)
            kind = DimensionTypeEnum.kHorizontalDimensionType
        Else
            textPoint = tg.CreatePoint2d(view.Position.X - view.Width / 2 - 1.3, (minValue + maxValue) / 2)
            kind = DimensionTypeEnum.kVerticalDimensionType
        End If
        sheet.DrawingDimensions.GeneralDimensions.AddLinear(textPoint, sheet.CreateGeometryIntent(minCurve), sheet.CreateGeometryIntent(maxCurve), kind)
    Catch
    End Try
End Sub

Sub TryAddPartsList(sheet As Sheet, front As DrawingView, tg As TransientGeometry)
    Try
        sheet.PartsLists.Add(front, tg.CreatePoint2d(2.2, sheet.Height - 1.8))
    Catch
    End Try
End Sub

Sub TryAddBalloons(sheet As Sheet, model As Document, iso As DrawingView, tg As TransientGeometry)
    Try
        Dim asm As AssemblyDocument = model
        Dim used As Double = iso.Position.Y + iso.Height / 2
        For Each occ As ComponentOccurrence In asm.ComponentDefinition.Occurrences
            If occ.Suppressed Then Continue For
            Dim curves As DrawingCurvesEnumerator = Nothing
            Try
                curves = iso.DrawingCurves(occ)
            Catch
                curves = Nothing
            End Try
            If curves Is Nothing OrElse curves.Count = 0 Then Continue For
            Dim curve As DrawingCurve = curves.Item(1)
            Dim attach As Point2d = Nothing
            Try
                attach = curve.MidPoint
            Catch
                attach = Nothing
            End Try
            If attach Is Nothing Then Continue For
            used -= 0.9
            Dim tip As Point2d = tg.CreatePoint2d(iso.Position.X + iso.Width / 2 + 1.6, used)
            Dim points As ObjectCollection = ThisApplication.TransientObjects.CreateObjectCollection()
            points.Add(attach)
            points.Add(tip)
            sheet.Balloons.Add(points)
        Next
    Catch
    End Try
End Sub

Function SaveDrawing(drawDoc As DrawingDocument, model As Document) As String
    Dim path As String = OutputPath(model, ".idw")
    drawDoc.SaveAs(path, False)
    Return path
End Function

Function WriteCurves(model As Document, views As Dictionary(Of String, DrawingView)) As String
    Dim path As String = OutputPath(model, ".drawgen.json")
    Dim culture = System.Globalization.CultureInfo.InvariantCulture
    Dim box As Box = model.ComponentDefinition.RangeBox
    Dim lengthIn As Double = Math.Abs(box.MaxPoint.X - box.MinPoint.X) / 2.54
    Dim heightIn As Double = Math.Abs(box.MaxPoint.Y - box.MinPoint.Y) / 2.54
    Dim widthIn As Double = Math.Abs(box.MaxPoint.Z - box.MinPoint.Z) / 2.54
    Dim fileKind As String = "ipt"
    Dim modelKind As String = "part"
    If model.DocumentType = DocumentTypeEnum.kAssemblyDocumentObject Then
        fileKind = "iam"
        modelKind = "assembly"
    End If
    Dim viewBody As New StringBuilder()
    Dim firstView As Boolean = True
    For Each pair As KeyValuePair(Of String, DrawingView) In views
        If Not firstView Then viewBody.Append(",")
        firstView = False
        Dim includeDims As Boolean = True
        If pair.Key = "iso" Then includeDims = False
        Dim oneView As String = FormatView(pair.Value, includeDims, culture)
        viewBody.Append(Quoted(pair.Key))
        viewBody.Append(":")
        viewBody.Append(oneView)
    Next
    Dim bom As String = ""
    If fileKind = "iam" Then bom = BomJson(model)
    Dim json As New StringBuilder()
    json.Append("{")
    json.Append(Quoted("schema"))
    json.Append(":")
    json.Append(Quoted("drawgen/1"))
    json.Append(",")
    json.Append(Quoted("fileName"))
    json.Append(":")
    json.Append(Quoted(System.IO.Path.GetFileName(model.FullFileName)))
    json.Append(",")
    json.Append(Quoted("fileKind"))
    json.Append(":")
    json.Append(Quoted(fileKind))
    json.Append(",")
    json.Append(Quoted("selectedViews"))
    json.Append(":[")
    json.Append(Quoted("front"))
    json.Append(",")
    json.Append(Quoted("top"))
    json.Append(",")
    json.Append(Quoted("side"))
    json.Append(",")
    json.Append(Quoted("iso"))
    json.Append("],")
    json.Append(Quoted("properties"))
    json.Append(":{")
    json.Append(Quoted("partNumber"))
    json.Append(":")
    json.Append(Quoted(Prop(model, "Design Tracking Properties", "Part Number")))
    json.Append(",")
    json.Append(Quoted("description"))
    json.Append(":")
    json.Append(Quoted(Prop(model, "Design Tracking Properties", "Description")))
    json.Append(",")
    json.Append(Quoted("material"))
    json.Append(":")
    json.Append(Quoted(Prop(model, "Design Tracking Properties", "Material")))
    json.Append(",")
    json.Append(Quoted("designer"))
    json.Append(":")
    json.Append(Quoted(Prop(model, "Design Tracking Properties", "Designer")))
    json.Append(",")
    json.Append(Quoted("drawnBy"))
    json.Append(":")
    json.Append(Quoted(Prop(model, "Inventor Summary Information", "Author")))
    json.Append(",")
    json.Append(Quoted("scale"))
    json.Append(":")
    json.Append(Quoted("SEE ABOVE"))
    json.Append("},")
    json.Append(Quoted("model"))
    json.Append(":{")
    json.Append(Quoted("kind"))
    json.Append(":")
    json.Append(Quoted(modelKind))
    json.Append(",")
    json.Append(Quoted("overall"))
    json.Append(":{")
    json.Append(Quoted("length"))
    json.Append(":")
    json.Append(Num(lengthIn, culture))
    json.Append(",")
    json.Append(Quoted("width"))
    json.Append(":")
    json.Append(Num(widthIn, culture))
    json.Append(",")
    json.Append(Quoted("height"))
    json.Append(":")
    json.Append(Num(heightIn, culture))
    json.Append("},")
    json.Append(Quoted("bends"))
    json.Append(":[],")
    json.Append(Quoted("components"))
    json.Append(":[")
    json.Append(bom)
    json.Append("],")
    json.Append(Quoted("views"))
    json.Append(":{")
    json.Append(viewBody.ToString())
    json.Append("}}}")
    System.IO.File.WriteAllText(path, json.ToString(), New UTF8Encoding(False))
    Return "Curves: " & path
End Function

Function FormatView(view As DrawingView, includeDims As Boolean, culture As System.Globalization.CultureInfo) As String
    Dim paths As New StringBuilder()
    Dim first As Boolean = True
    Dim minX As Double = 1.0E+30
    Dim minY As Double = 1.0E+30
    Dim maxX As Double = -1.0E+30
    Dim maxY As Double = -1.0E+30
    Dim count As Integer = 0
    For Each curve As DrawingCurve In view.DrawingCurves
        Dim hidden As Boolean = False
        Try
            If curve.Segments.Count > 0 Then hidden = curve.Segments.Item(1).HiddenLine
        Catch
        End Try
        Dim pts As List(Of Point2d) = CurvePoints(curve)
        If pts.Count < 2 Then Continue For
        If Not first Then paths.Append(",")
        first = False
        Dim layer As String = "OBJECT"
        Dim dashed As String = "false"
        If hidden Then
            layer = "HIDDEN"
            dashed = "true"
        End If
        paths.Append("{")
        paths.Append(Quoted("pts"))
        paths.Append(":[")
        Dim i As Integer = 0
        Do While i < pts.Count
            Dim local() As Double = ModelInches(view, pts(i))
            If i > 0 Then paths.Append(",")
            paths.Append("[")
            paths.Append(Num(local(0), culture))
            paths.Append(",")
            paths.Append(Num(local(1), culture))
            paths.Append("]")
            minX = Math.Min(minX, local(0))
            minY = Math.Min(minY, local(1))
            maxX = Math.Max(maxX, local(0))
            maxY = Math.Max(maxY, local(1))
            count = count + 1
            i = i + 1
        Loop
        paths.Append("],")
        paths.Append(Quoted("layer"))
        paths.Append(":")
        paths.Append(Quoted(layer))
        paths.Append(",")
        paths.Append(Quoted("dashed"))
        paths.Append(":")
        paths.Append(dashed)
        paths.Append("}")
    Next
    Dim dims As String = ""
    If includeDims AndAlso count > 0 AndAlso maxX > minX AndAlso maxY > minY Then
        Dim across As String = AxisDim("horizontal", "x1", minX, "x2", maxX, "y", minY, maxX - minX, culture)
        Dim upward As String = AxisDim("vertical", "y1", minY, "y2", maxY, "x", minX, maxY - minY, culture)
        dims = across & "," & upward
    End If
    Dim result As New StringBuilder()
    result.Append("{")
    result.Append(Quoted("paths"))
    result.Append(":[")
    result.Append(paths.ToString())
    result.Append("],")
    result.Append(Quoted("dims"))
    result.Append(":[")
    result.Append(dims)
    result.Append("]}")
    Return result.ToString()
End Function

Function AxisDim(kind As String, aKey As String, aValue As Double, bKey As String, bValue As Double, cKey As String, cValue As Double, span As Double, culture As System.Globalization.CultureInfo) As String
    Dim item As New StringBuilder()
    item.Append("{")
    item.Append(Quoted("kind"))
    item.Append(":")
    item.Append(Quoted(kind))
    item.Append(",")
    item.Append(Quoted(aKey))
    item.Append(":")
    item.Append(Num(aValue, culture))
    item.Append(",")
    item.Append(Quoted(bKey))
    item.Append(":")
    item.Append(Num(bValue, culture))
    item.Append(",")
    item.Append(Quoted(cKey))
    item.Append(":")
    item.Append(Num(cValue, culture))
    item.Append(",")
    item.Append(Quoted("text"))
    item.Append(":")
    item.Append(Quoted(Num(span, culture)))
    item.Append("}")
    Return item.ToString()
End Function

Function CurvePoints(curve As DrawingCurve) As List(Of Point2d)
    Dim pts As New List(Of Point2d)
    Dim kind As String = ""
    Try
        kind = curve.CurveType.ToString()
    Catch
    End Try
    Try
        If kind.Contains("Circle") AndAlso Not kind.Contains("Arc") Then
            Dim center As Point2d = curve.CenterPoint
            Dim radius As Double = center.DistanceTo(curve.StartPoint)
            AddArcSamples(pts, center, radius, 0, 2 * HalfTurn(), 16)
            Return pts
        End If
        If kind.Contains("Arc") OrElse kind.Contains("Ellipse") OrElse kind.Contains("Spline") OrElse kind.Contains("BSpline") Then
            Dim center As Point2d = Nothing
            Try
                center = curve.CenterPoint
            Catch
                center = Nothing
            End Try
            If center IsNot Nothing Then
                Dim startA As Double = Math.Atan2(curve.StartPoint.Y - center.Y, curve.StartPoint.X - center.X)
                Dim endA As Double = Math.Atan2(curve.EndPoint.Y - center.Y, curve.EndPoint.X - center.X)
                Dim midA As Double = Math.Atan2(curve.MidPoint.Y - center.Y, curve.MidPoint.X - center.X)
                Dim radius As Double = center.DistanceTo(curve.StartPoint)
                Dim sweep As Double = SweepThrough(startA, endA, midA)
                AddArcSamples(pts, center, radius, startA, sweep, 8)
                Return pts
            End If
        End If
    Catch
    End Try
    Try
        pts.Add(curve.StartPoint)
        pts.Add(curve.EndPoint)
    Catch
    End Try
    Return pts
End Function

Function SweepThrough(startA As Double, endA As Double, midA As Double) As Double
    Dim turn As Double = 2 * HalfTurn()
    Dim forward As Double = endA - startA
    Do While forward <= 0
        forward = forward + turn
    Loop
    Do While forward > turn
        forward = forward - turn
    Loop
    Dim back As Double = forward - turn
    Dim midForward As Double = midA - startA
    Do While midForward < 0
        midForward = midForward + turn
    Loop
    Do While midForward > turn
        midForward = midForward - turn
    Loop
    If midForward <= forward + 0.01 Then Return forward
    Return back
End Function

Sub AddArcSamples(pts As List(Of Point2d), center As Point2d, radius As Double, startAngle As Double, sweepAngle As Double, count As Integer)
    Dim k As Integer = 0
    Do While k <= count
        Dim angle As Double = startAngle + sweepAngle * k / CDbl(count)
        Dim px As Double = center.X + radius * CosineOf(angle)
        Dim py As Double = center.Y + radius * SineOf(angle)
        Dim sample As Point2d = ThisApplication.TransientGeometry.CreatePoint2d(px, py)
        pts.Add(sample)
        k = k + 1
    Loop
End Sub

Function HalfTurn() As Double
    Return 3.14159265358979
End Function

Function SineOf(angle As Double) As Double
    Dim p As Double = HalfTurn()
    Dim turn As Double = 2 * p
    Dim reduced As Double = angle
    Do While reduced > p
        reduced = reduced - turn
    Loop
    Do While reduced < -p
        reduced = reduced + turn
    Loop
    Dim term As Double = reduced
    Dim sum As Double = reduced
    Dim n As Integer = 1
    Do While n <= 10
        Dim denom As Double = (2 * n) * (2 * n + 1)
        term = -term * reduced * reduced / denom
        sum = sum + term
        n = n + 1
    Loop
    Return sum
End Function

Function CosineOf(angle As Double) As Double
    Return SineOf(angle + HalfTurn() / 2)
End Function

Function ModelInches(view As DrawingView, point As Point2d) As Double()
    Dim x As Double = (point.X - view.Position.X) / view.Scale / 2.54
    Dim y As Double = (point.Y - view.Position.Y) / view.Scale / 2.54
    Return New Double() {x, y}
End Function

Function BomJson(model As Document) As String
    Dim asm As AssemblyDocument = model
    Dim view As BOMView = asm.ComponentDefinition.BOM.BOMViews.Item("Structured")
    Dim bom As New StringBuilder()
    Dim index As Integer = 0
    For Each row As BOMRow In view.BOMRows
        If row.ComponentDefinitions.Count = 0 Then Continue For
        Dim child As Document = row.ComponentDefinitions.Item(1).Document
        If index > 0 Then bom.Append(",")
        index += 1
        Dim itemNo As String = CStr(row.ItemNumber)
        If itemNo = "" Then itemNo = index.ToString()
        bom.Append("{")
        bom.Append(Quoted("item"))
        bom.Append(":")
        bom.Append(Quoted(itemNo))
        bom.Append(",")
        bom.Append(Quoted("partNumber"))
        bom.Append(":")
        bom.Append(Quoted(Prop(child, "Design Tracking Properties", "Part Number")))
        bom.Append(",")
        bom.Append(Quoted("description"))
        bom.Append(":")
        bom.Append(Quoted(Prop(child, "Design Tracking Properties", "Description")))
        bom.Append(",")
        bom.Append(Quoted("qty"))
        bom.Append(":")
        bom.Append(Quoted(CStr(row.ItemQuantity)))
        bom.Append("}")
    Next
    Return bom.ToString()
End Function

Function OutputPath(model As Document, extension As String) As String
    Dim folder As String = System.IO.Path.GetDirectoryName(model.FullFileName)
    Dim parent As String = System.IO.Path.GetDirectoryName(folder)
    If parent <> "" Then
        Dim drawingFolder As String = System.IO.Path.Combine(parent, "Drawing")
        If System.IO.Directory.Exists(drawingFolder) Then folder = drawingFolder
    End If
    Dim partNo As String = Prop(model, "Design Tracking Properties", "Part Number")
    If partNo = "" Then partNo = System.IO.Path.GetFileNameWithoutExtension(model.FullFileName)
    Dim stem As String = SafeFile(partNo)
    Dim path As String = System.IO.Path.Combine(folder, stem & extension)
    If Not System.IO.File.Exists(path) Then Return path
    path = System.IO.Path.Combine(folder, stem & "-generated" & extension)
    Dim n As Integer = 2
    While System.IO.File.Exists(path)
        path = System.IO.Path.Combine(folder, stem & "-generated-" & n.ToString() & extension)
        n += 1
    End While
    Return path
End Function

Function SafeFile(value As String) As String
    Dim cleaned As String = value
    For Each ch As Char In System.IO.Path.GetInvalidFileNameChars()
        cleaned = cleaned.Replace(ch, "-"c)
    Next
    cleaned = cleaned.Trim()
    If cleaned = "" Then cleaned = "Drawing"
    Return cleaned
End Function

Function Prop(doc As Document, setName As String, propName As String) As String
    Try
        Return CStr(doc.PropertySets.Item(setName).Item(propName).Value)
    Catch
        Return ""
    End Try
End Function

Function Quoted(value As String) As String
    Return Chr(34) & JsonEscape(value) & Chr(34)
End Function

Function JsonEscape(value As String) As String
    If value Is Nothing Then Return ""
    Dim slash As String = Chr(92)
    Dim mark As String = Chr(34)
    Dim cleaned As String = value
    cleaned = cleaned.Replace(slash, slash & slash)
    cleaned = cleaned.Replace(mark, slash & mark)
    cleaned = cleaned.Replace(vbCr, " ")
    cleaned = cleaned.Replace(vbLf, " ")
    Return cleaned
End Function

Function Num(value As Double, culture As System.Globalization.CultureInfo) As String
    Return value.ToString("0.###", culture)
End Function

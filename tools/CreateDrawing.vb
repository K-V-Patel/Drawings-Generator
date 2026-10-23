' CreateDrawing.vb
' iLogic rule. Run it from an open part (.ipt) or assembly (.iam).
'
' Creates a drawing from TemplateName, so the border, title block, and
' dimension style are the Inventor template. Inventor places the front,
' top, and right views, plus an isometric, and adds overall dimensions.
' An assembly also gets a parts list. When it has more than one part,
' each part gets an item balloon.
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
    ' Drawing template. Use a file name from the Inventor template folder,
    ' or a full path. Standard.idw is the usual shop template.
    Dim TemplateName As String = "Standard.idw"

    Dim model As Document = ThisDoc.Document
    If model.DocumentType <> DocumentTypeEnum.kPartDocumentObject AndAlso model.DocumentType <> DocumentTypeEnum.kAssemblyDocumentObject Then
        MessageBox.Show("Open a part (.ipt) or an assembly (.iam), then run this rule.", "Drawings Generator")
        Return
    End If
    If String.IsNullOrEmpty(model.FullFileName) Then
        MessageBox.Show("Save the model first. The drawing is named from its part number.", "Drawings Generator")
        Return
    End If

    Dim templatePath As String = FindTemplate(TemplateName)
    If templatePath = "" Then
        MessageBox.Show(TemplateName & " was not found in the Inventor template folder.", "Drawings Generator")
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

        Dim balloonNote As String = ""
        If model.DocumentType = DocumentTypeEnum.kAssemblyDocumentObject Then
            ShowAssemblyParts(sheet, views)
            TryAddPartsList(sheet, views("front"), tg)
            drawDoc.Update()
            balloonNote = AddItemBalloons(sheet, model, views, tg)
        End If
        drawDoc.Update()

        Dim idwPath As String = SaveDrawing(drawDoc, model)
        Dim jsonNote As String = ""
        Try
            jsonNote = WriteCurves(model, views)
        Catch ex As Exception
            jsonNote = "View curves were not written: " & ex.Message
        End Try
        Dim done As String = "Created " & idwPath & vbLf & jsonNote
        If balloonNote <> "" Then done = done & vbLf & balloonNote
        MessageBox.Show(done, "Drawings Generator")
    Catch ex As Exception
        MessageBox.Show("Could not create the drawing: " & ex.Message, "Drawings Generator")
    Finally
        app.ScreenUpdating = previous
    End Try
End Sub

Function FindTemplate(templateFile As String) As String
    If templateFile = "" Then Return ""
    If templateFile.Contains("\") OrElse templateFile.Contains("/") Then
        If System.IO.File.Exists(templateFile) Then Return templateFile
        Return ""
    End If
    Dim candidates As New List(Of String)
    Try
        Dim folder As String = ThisApplication.DesignProjectManager.ActiveDesignProject.TemplatesPath
        candidates.Add(System.IO.Path.Combine(folder, "en-US", templateFile))
        candidates.Add(System.IO.Path.Combine(folder, templateFile))
    Catch
    End Try
    candidates.Add(System.IO.Path.Combine("C:\Users\Public\Documents\Autodesk\Inventor 2025\Templates\en-US", templateFile))
    candidates.Add(System.IO.Path.Combine("C:\Users\Public\Documents\Autodesk\Inventor 2026\Templates\en-US", templateFile))
    candidates.Add(System.IO.Path.Combine("C:\Users\Public\Documents\Autodesk\Inventor 2024\Templates\en-US", templateFile))
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

Function AddItemBalloons(sheet As Sheet, model As Document, views As Dictionary(Of String, DrawingView), tg As TransientGeometry) As String
    Try
        Dim asm As AssemblyDocument = model
        Dim occurrenceCount As Integer = CountOccurrences(asm)
        Dim targets As List(Of ComponentOccurrence) = BalloonTargets(asm)
        If targets.Count = 0 Then targets = DistinctOccurrences(asm)
        If occurrenceCount < 2 AndAlso targets.Count < 2 Then Return ""
        If targets.Count = 0 Then Return ""
        ShowAssemblyParts(sheet, views)
        Dim pitch As Double = BalloonPitch(views, targets.Count)
        Dim nextY As New Dictionary(Of String, Double)
        Dim placed As Integer = 0
        Dim problem As String = ""
        Dim roles As New List(Of String)
        roles.Add("iso")
        roles.Add("front")
        roles.Add("side")
        roles.Add("top")
        For Each occ As ComponentOccurrence In targets
            Dim failure As String = BalloonOne(sheet, views, occ, tg, pitch, nextY, roles)
            If failure = "" Then
                placed = placed + 1
            Else
                problem = failure
            End If
        Next
        If placed > 0 Then Return "Balloons: " & placed.ToString()
        If problem = "" Then problem = "No part curve was available to attach."
        Return "Balloons were not placed. " & problem
    Catch ex As Exception
        Return "Balloons were not placed. " & ex.Message
    End Try
End Function

Function BalloonPitch(views As Dictionary(Of String, DrawingView), count As Integer) As Double
    Dim pitch As Double = 1.2
    If Not views.ContainsKey("iso") Then Return pitch
    If count < 2 Then Return pitch
    Dim iso As DrawingView = views("iso")
    Dim room As Double = iso.Position.Y + iso.Height / 2 - 1.5
    If room <= 0 Then Return pitch
    Dim needed As Double = pitch * (count - 1)
    If needed > room Then pitch = room / (count - 1)
    If pitch < 0.8 Then pitch = 0.8
    Return pitch
End Function

Function CountOccurrences(asm As AssemblyDocument) As Integer
    Dim count As Integer = 0
    For Each occ As ComponentOccurrence In asm.ComponentDefinition.Occurrences
        If occ.Suppressed Then Continue For
        count = count + 1
    Next
    Return count
End Function

Function BalloonTargets(asm As AssemblyDocument) As List(Of ComponentOccurrence)
    Dim targets As New List(Of ComponentOccurrence)
    Try
        Dim bomView As BOMView = asm.ComponentDefinition.BOM.BOMViews.Item("Structured")
        For Each row As BOMRow In bomView.BOMRows
            If row.ComponentDefinitions.Count = 0 Then Continue For
            Dim occ As ComponentOccurrence = FindOccurrence(asm, row.ComponentDefinitions.Item(1))
            If occ IsNot Nothing Then targets.Add(occ)
        Next
    Catch
    End Try
    Return targets
End Function

Function DistinctOccurrences(asm As AssemblyDocument) As List(Of ComponentOccurrence)
    Dim targets As New List(Of ComponentOccurrence)
    Dim seen As New List(Of String)
    For Each occ As ComponentOccurrence In asm.ComponentDefinition.Occurrences
        If occ.Suppressed Then Continue For
        Dim key As String = PartKey(occ)
        If key = "" Then Continue For
        If seen.Contains(key) Then Continue For
        seen.Add(key)
        targets.Add(occ)
    Next
    Return targets
End Function

Function FindOccurrence(asm As AssemblyDocument, def As ComponentDefinition) As ComponentOccurrence
    For Each occ As ComponentOccurrence In asm.ComponentDefinition.Occurrences
        If occ.Suppressed Then Continue For
        If SameDefinition(occ, def) Then Return occ
    Next
    Return Nothing
End Function

Function SameDefinition(occ As ComponentOccurrence, def As ComponentDefinition) As Boolean
    Try
        If occ.Definition Is def Then Return True
    Catch
    End Try
    Try
        Dim occDoc As Document = occ.Definition.Document
        Dim defDoc As Document = def.Document
        If occDoc Is defDoc Then Return True
        If occDoc.FullFileName <> "" AndAlso occDoc.FullFileName = defDoc.FullFileName Then Return True
    Catch
    End Try
    Return False
End Function

Function PartKey(occ As ComponentOccurrence) As String
    Try
        Dim full As String = occ.Definition.Document.FullFileName
        If full <> "" Then Return full
    Catch
    End Try
    Try
        Return occ.Name
    Catch
    End Try
    Return ""
End Function

Sub ShowAssemblyParts(sheet As Sheet, views As Dictionary(Of String, DrawingView))
    Try
        Dim drawDoc As DrawingDocument = sheet.Parent
        For Each view As DrawingView In views.Values
            Try
                view.WeldmentState = WeldmentStateEnum.kAssemblyWeldmentState
            Catch
            End Try
        Next
        drawDoc.Update()
    Catch
    End Try
End Sub

Function BalloonOne(sheet As Sheet, views As Dictionary(Of String, DrawingView), occ As ComponentOccurrence, tg As TransientGeometry, pitch As Double, nextY As Dictionary(Of String, Double), roles As List(Of String)) As String
    Dim lastProblem As String = "No part curve was available to attach."
    For Each role As String In roles
        If Not views.ContainsKey(role) Then Continue For
        Dim host As DrawingView = views(role)
        Dim curves As List(Of DrawingCurve) = CurvesForPart(host, occ)
        Dim limit As Integer = curves.Count
        If limit > 8 Then limit = 8
        Dim index As Integer = 0
        Do While index < limit
            Dim curve As DrawingCurve = curves(index)
            index = index + 1
            Dim tip As Point2d = BalloonTip(sheet, host, role, nextY, tg)
            Dim failure As String = PlaceBalloon(sheet, curve, tip)
            If failure = "" Then
                nextY(role) = nextY(role) - pitch
                Return ""
            End If
            lastProblem = failure
        Loop
    Next
    Return lastProblem
End Function

Function CurvesForPart(view As DrawingView, occ As ComponentOccurrence) As List(Of DrawingCurve)
    Dim lines As New List(Of DrawingCurve)
    Dim hiddenLines As New List(Of DrawingCurve)
    Dim others As New List(Of DrawingCurve)
    CollectPartCurves(view, occ, lines, hiddenLines, others, True)
    If lines.Count = 0 AndAlso hiddenLines.Count = 0 AndAlso others.Count = 0 Then
        CollectPartCurves(view, occ, lines, hiddenLines, others, False)
    End If
    For Each curve As DrawingCurve In hiddenLines
        lines.Add(curve)
    Next
    For Each curve As DrawingCurve In others
        lines.Add(curve)
    Next
    Return lines
End Function

Sub CollectPartCurves(view As DrawingView, occ As ComponentOccurrence, lines As List(Of DrawingCurve), hiddenLines As List(Of DrawingCurve), others As List(Of DrawingCurve), directOnly As Boolean)
    Try
        Dim curves As DrawingCurvesEnumerator = Nothing
        If directOnly Then
            curves = view.DrawingCurves(occ)
        Else
            curves = view.DrawingCurves
        End If
        If curves Is Nothing Then Return
        For Each curve As DrawingCurve In curves
            If Not directOnly AndAlso Not SameOccurrence(CurveOwner(curve), occ) Then Continue For
            If IsLine(curve) AndAlso Not IsHidden(curve) Then
                lines.Add(curve)
            ElseIf IsLine(curve) Then
                hiddenLines.Add(curve)
            Else
                others.Add(curve)
            End If
        Next
    Catch
    End Try
End Sub

Function IsHidden(curve As DrawingCurve) As Boolean
    Try
        If curve.Segments Is Nothing OrElse curve.Segments.Count = 0 Then Return False
        Return curve.Segments.Item(1).HiddenLine
    Catch
        Return False
    End Try
End Function

Function IsLine(curve As DrawingCurve) As Boolean
    Try
        Dim kind As String = curve.CurveType.ToString()
        If kind.Contains("Line") Then Return True
    Catch
    End Try
    Return False
End Function

Function BalloonTip(sheet As Sheet, host As DrawingView, role As String, nextY As Dictionary(Of String, Double), tg As TransientGeometry) As Point2d
    If Not nextY.ContainsKey(role) Then
        Dim startY As Double = host.Position.Y + host.Height / 2
        If startY > sheet.Height - 2.0 Then startY = sheet.Height - 2.0
        nextY(role) = startY
    End If
    Dim tipY As Double = nextY(role)
    If tipY < 2.0 Then tipY = 2.0
    Dim tipX As Double = host.Position.X - host.Width / 2 - 1.8
    If tipX < 2.0 Then tipX = host.Position.X + host.Width / 2 + 1.8
    If tipX > sheet.Width - 2.0 Then tipX = sheet.Width - 2.0
    If tipX < 2.0 Then tipX = 2.0
    Return tg.CreatePoint2d(tipX, tipY)
End Function

Function CurveOwner(curve As DrawingCurve) As ComponentOccurrence
    Dim geom As Object = Nothing
    Try
        geom = curve.ModelGeometry
    Catch
        Return Nothing
    End Try
    If geom Is Nothing Then Return Nothing
    Try
        Dim occ As Object = CallByName(geom, "ContainingOccurrence", CallType.Get)
        Return occ
    Catch
        Return Nothing
    End Try
End Function

Function SameOccurrence(leftOcc As ComponentOccurrence, rightOcc As ComponentOccurrence) As Boolean
    If leftOcc Is Nothing OrElse rightOcc Is Nothing Then Return False
    Try
        If leftOcc Is rightOcc Then Return True
    Catch
    End Try
    Try
        If leftOcc.Name = rightOcc.Name Then Return True
    Catch
    End Try
    Try
        Return SameDefinition(leftOcc, rightOcc.Definition)
    Catch
        Return False
    End Try
End Function

Function PlaceBalloon(sheet As Sheet, curve As DrawingCurve, tip As Point2d) As String
    Dim attach As Point2d = PointOnCurve(curve)
    If attach Is Nothing Then Return "The part curve has no attach point."
    Dim problem As String = "The part curve has no attach point."
    Dim mode As Integer = 0
    Do While mode <= 2
        Dim attempt As String = AttachBalloon(sheet, curve, attach, tip, mode)
        If attempt = "" Then Return ""
        problem = attempt
        mode = mode + 1
    Loop
    Return problem
End Function

Function AttachBalloon(sheet As Sheet, curve As DrawingCurve, attach As Point2d, tip As Point2d, mode As Integer) As String
    Dim intent As GeometryIntent = MakeIntent(sheet, curve, attach, mode)
    If intent Is Nothing Then Return "The part curve has no attach point."
    ' Inventor's balloon sample places the symbol, then a bend, then the edge.
    Dim bent As String = CommitBalloon(sheet, BuildLeader(tip, attach, intent, True), False)
    If bent = "" Then Return ""
    Dim bentLevel As String = CommitBalloon(sheet, BuildLeader(tip, attach, intent, True), True)
    If bentLevel = "" Then Return ""
    Dim straight As String = CommitBalloon(sheet, BuildLeader(tip, attach, intent, False), False)
    If straight = "" Then Return ""
    Return bent
End Function

Function MakeIntent(sheet As Sheet, curve As DrawingCurve, attach As Point2d, mode As Integer) As GeometryIntent
    Try
        If mode = 1 Then
            Dim param As Double = 0.5
            Return sheet.CreateGeometryIntent(curve, param)
        End If
        If mode = 2 Then
            Return sheet.CreateGeometryIntent(curve, PointIntentEnum.kMidPointIntent)
        End If
        Return sheet.CreateGeometryIntent(curve, attach)
    Catch
        Return Nothing
    End Try
End Function

Function BuildLeader(tip As Point2d, attach As Point2d, intent As GeometryIntent, useElbow As Boolean) As ObjectCollection
    Dim points As ObjectCollection = ThisApplication.TransientObjects.CreateObjectCollection()
    points.Add(tip)
    If useElbow Then
        Dim elbow As Point2d = LeaderElbow(tip, attach)
        If elbow IsNot Nothing Then points.Add(elbow)
    End If
    points.Add(intent)
    Return points
End Function

Function LeaderElbow(tip As Point2d, attach As Point2d) As Point2d
    If tip Is Nothing OrElse attach Is Nothing Then Return Nothing
    Dim dx As Double = attach.X - tip.X
    Dim dy As Double = attach.Y - tip.Y
    Dim elbowX As Double = tip.X
    Dim elbowY As Double = tip.Y
    If Math.Abs(dx) >= Math.Abs(dy) Then
        elbowX = tip.X + dx * 0.65
    Else
        elbowY = tip.Y + dy * 0.65
    End If
    If Math.Abs(elbowX - tip.X) < 0.3 AndAlso Math.Abs(elbowY - tip.Y) < 0.3 Then Return Nothing
    If Math.Abs(elbowX - attach.X) < 0.15 AndAlso Math.Abs(elbowY - attach.Y) < 0.15 Then Return Nothing
    Return ThisApplication.TransientGeometry.CreatePoint2d(elbowX, elbowY)
End Function

Function CommitBalloon(sheet As Sheet, points As ObjectCollection, useLevel As Boolean) As String
    Try
        If useLevel Then
            ' Used only when this drawing has no parts list yet. A missing slot, not a null.
            sheet.Balloons.Add(points, System.Type.Missing, PartsListLevelEnum.kStructured)
        Else
            sheet.Balloons.Add(points)
        End If
        Return ""
    Catch ex As Exception
        Return ex.Message
    End Try
End Function

Function PointOnCurve(curve As DrawingCurve) As Point2d
    Try
        Dim mid As Point2d = curve.MidPoint
        If mid IsNot Nothing Then Return mid
    Catch
    End Try
    Try
        If curve.Segments IsNot Nothing AndAlso curve.Segments.Count > 0 Then
            Dim startPt As Point2d = curve.Segments.Item(1).StartPoint
            If startPt IsNot Nothing Then Return startPt
        End If
    Catch
    End Try
    Return Nothing
End Function

Function SaveDrawing(drawDoc As DrawingDocument, model As Document) As String
    Dim path As String = OutputPath(model, ".idw")
    drawDoc.SaveAs(path, False)
    Return path
End Function

Function WriteCurves(model As Document, views As Dictionary(Of String, DrawingView)) As String
    Dim path As String = OutputPath(model, ".drawgen.json")
    Dim culture = System.Globalization.CultureInfo.InvariantCulture
    Dim lengthIn As Double = 0
    Dim heightIn As Double = 0
    Dim widthIn As Double = 0
    Try
        Dim box As Box = model.ComponentDefinition.RangeBox
        If box IsNot Nothing AndAlso box.MaxPoint IsNot Nothing AndAlso box.MinPoint IsNot Nothing Then
            lengthIn = Math.Abs(box.MaxPoint.X - box.MinPoint.X) / 2.54
            heightIn = Math.Abs(box.MaxPoint.Y - box.MinPoint.Y) / 2.54
            widthIn = Math.Abs(box.MaxPoint.Z - box.MinPoint.Z) / 2.54
        End If
    Catch
    End Try
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
    Dim viewCurves As DrawingCurvesEnumerator = Nothing
    Try
        viewCurves = view.DrawingCurves
    Catch
        viewCurves = Nothing
    End Try
    If viewCurves IsNot Nothing Then
    For Each curve As DrawingCurve In viewCurves
        Try
        Dim hidden As Boolean = False
        Try
            If curve.Segments IsNot Nothing AndAlso curve.Segments.Count > 0 Then hidden = curve.Segments.Item(1).HiddenLine
        Catch
        End Try
        Dim pts As List(Of Point2d) = CurvePoints(curve)
        If pts Is Nothing OrElse pts.Count < 2 Then Continue For
        Dim coords As New StringBuilder()
        Dim wrotePoint As Boolean = False
        Dim pointCount As Integer = 0
        Dim i As Integer = 0
        Do While i < pts.Count
            Dim local() As Double = ModelInches(view, pts(i))
            i = i + 1
            If local Is Nothing Then Continue Do
            If wrotePoint Then coords.Append(",")
            wrotePoint = True
            coords.Append("[")
            coords.Append(Num(local(0), culture))
            coords.Append(",")
            coords.Append(Num(local(1), culture))
            coords.Append("]")
            minX = Math.Min(minX, local(0))
            minY = Math.Min(minY, local(1))
            maxX = Math.Max(maxX, local(0))
            maxY = Math.Max(maxY, local(1))
            pointCount = pointCount + 1
        Loop
        If pointCount < 2 Then Continue For
        count = count + pointCount
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
        paths.Append(coords.ToString())
        paths.Append("],")
        paths.Append(Quoted("layer"))
        paths.Append(":")
        paths.Append(Quoted(layer))
        paths.Append(",")
        paths.Append(Quoted("dashed"))
        paths.Append(":")
        paths.Append(dashed)
        paths.Append("}")
        Catch
        End Try
    Next
    End If
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
            Dim center As Point2d = Nothing
            Dim startPt As Point2d = Nothing
            Try
                center = curve.CenterPoint
            Catch
                center = Nothing
            End Try
            Try
                startPt = curve.StartPoint
            Catch
                startPt = Nothing
            End Try
            If center IsNot Nothing AndAlso startPt IsNot Nothing Then
                Dim radius As Double = center.DistanceTo(startPt)
                AddArcSamples(pts, center, radius, 0, 2 * HalfTurn(), 16)
                Return pts
            End If
        End If
        If kind.Contains("Arc") OrElse kind.Contains("Ellipse") OrElse kind.Contains("Spline") OrElse kind.Contains("BSpline") Then
            Dim center As Point2d = Nothing
            Try
                center = curve.CenterPoint
            Catch
                center = Nothing
            End Try
            If center IsNot Nothing AndAlso curve.StartPoint IsNot Nothing AndAlso curve.EndPoint IsNot Nothing AndAlso curve.MidPoint IsNot Nothing Then
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
    Dim startPt As Point2d = Nothing
    Dim endPt As Point2d = Nothing
    Try
        startPt = curve.StartPoint
    Catch
        startPt = Nothing
    End Try
    Try
        endPt = curve.EndPoint
    Catch
        endPt = Nothing
    End Try
    If startPt IsNot Nothing Then pts.Add(startPt)
    If endPt IsNot Nothing Then pts.Add(endPt)
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
    If point Is Nothing OrElse view Is Nothing OrElse view.Position Is Nothing Then Return Nothing
    Dim scale As Double = view.Scale
    If scale = 0 Then Return Nothing
    Dim x As Double = (point.X - view.Position.X) / scale / 2.54
    Dim y As Double = (point.Y - view.Position.Y) / scale / 2.54
    Return New Double() {x, y}
End Function

Function BomJson(model As Document) As String
    Dim bom As New StringBuilder()
    Try
    Dim asm As AssemblyDocument = model
    Dim view As BOMView = asm.ComponentDefinition.BOM.BOMViews.Item("Structured")
    Dim index As Integer = 0
    For Each row As BOMRow In view.BOMRows
        Try
        If row.ComponentDefinitions.Count = 0 Then Continue For
        Dim def As ComponentDefinition = row.ComponentDefinitions.Item(1)
        If def Is Nothing OrElse def.Document Is Nothing Then Continue For
        Dim child As Document = def.Document
        If index > 0 Then bom.Append(",")
        index = index + 1
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
        Catch
        End Try
    Next
    Catch
    End Try
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

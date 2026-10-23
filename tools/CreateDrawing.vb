' CreateDrawing.vb
' iLogic rule. Run it from an open part (.ipt) or assembly (.iam).
'
' Creates a drawing from TemplateName, so the border, title block, and
' dimension style are the Inventor template. The front view follows the
' model ViewCube. Top and side are projected from that front view so they
' stay aligned. The isometric view uses the model Home view. Overall
' dimensions are added on the orthographic views.
' An assembly also gets a parts list. When it has more than one part,
' each part gets a balloon close beside that part on the isometric view.
' Item numbers are not stacked in order.
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
        ApplyFacing(front, model, "AppFrontViewCmd")
        QuietUpdate(drawDoc)
        front.Scale = FitScale(sheet, model, front)
        QuietUpdate(drawDoc)

        Dim views As New Dictionary(Of String, DrawingView)
        views("front") = front
        views("top") = sheet.DrawingViews.AddProjectedView(front, tg.CreatePoint2d(front.Position.X, front.Position.Y + front.Height), style)
        views("side") = sheet.DrawingViews.AddProjectedView(front, tg.CreatePoint2d(front.Position.X + front.Width, front.Position.Y), style)
        views("iso") = sheet.DrawingViews.AddBaseView( _
            model, tg.CreatePoint2d(sheet.Width * 0.75, sheet.Height * 0.68), _
            Math.Max(front.Scale * 0.75, 0.01), ViewOrientationTypeEnum.kIsoTopRightViewOrientation, style)
        ApplyHomeCamera(views("iso"), model)
        QuietUpdate(drawDoc)
        PositionViews(sheet, views, tg)
        QuietUpdate(drawDoc)
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
            QuietUpdate(drawDoc)
            balloonNote = AddItemBalloons(sheet, model, views, tg)
        End If
        QuietUpdate(drawDoc)

        Dim idwPath As String = ""
        Try
            idwPath = SaveDrawing(drawDoc, model)
        Catch ex As Exception
            MessageBox.Show("Could not save the drawing: " & ex.Message, "Drawings Generator")
            Return
        End Try
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

Sub ApplyHomeCamera(drawView As DrawingView, model As Document)
    ApplyFacing(drawView, model, "")
End Sub

Sub ApplyFacing(drawView As DrawingView, model As Document, commandName As String)
    ' Origin Front, Top, and Right stay in place when the ViewCube face cannot be read.
    Try
    If drawView Is Nothing OrElse model Is Nothing Then Return
    If model.Views.Count = 0 Then Return
    Dim modelView As Inventor.View = model.Views.Item(1)
    Dim live As Camera = modelView.Camera
    Dim eyeX As Double = live.Eye.X
    Dim eyeY As Double = live.Eye.Y
    Dim eyeZ As Double = live.Eye.Z
    Dim targetX As Double = live.Target.X
    Dim targetY As Double = live.Target.Y
    Dim targetZ As Double = live.Target.Z
    Dim upX As Double = live.UpVector.X
    Dim upY As Double = live.UpVector.Y
    Dim upZ As Double = live.UpVector.Z
    Dim wasPerspective As Boolean = live.Perspective
    Dim returnView As Inventor.View = Nothing
    Try
        returnView = ThisApplication.ActiveView
    Catch
    End Try
    Dim app As Inventor.Application = ThisApplication
    Dim wasUpdating As Boolean = app.ScreenUpdating
    Try
        If commandName = "" Then
            modelView.GoHome()
        Else
            app.ScreenUpdating = True
            modelView.Activate()
            app.CommandManager.ControlDefinitions.Item(commandName).Execute()
            modelView.Update()
            app.ScreenUpdating = wasUpdating
        End If
        Dim faceCam As Camera = modelView.Camera
        Dim faceEyeX As Double = faceCam.Eye.X
        Dim faceEyeY As Double = faceCam.Eye.Y
        Dim faceEyeZ As Double = faceCam.Eye.Z
        Dim faceTargetX As Double = faceCam.Target.X
        Dim faceTargetY As Double = faceCam.Target.Y
        Dim faceTargetZ As Double = faceCam.Target.Z
        Dim faceUpX As Double = faceCam.UpVector.X
        Dim faceUpY As Double = faceCam.UpVector.Y
        Dim faceUpZ As Double = faceCam.UpVector.Z
        Dim keepScale As Double = drawView.Scale
        Dim tg As TransientGeometry = app.TransientGeometry
        Dim drawCam As Camera = drawView.Camera
        drawCam.Eye = tg.CreatePoint(faceEyeX, faceEyeY, faceEyeZ)
        drawCam.Target = tg.CreatePoint(faceTargetX, faceTargetY, faceTargetZ)
        drawCam.UpVector = tg.CreateUnitVector(faceUpX, faceUpY, faceUpZ)
        drawCam.Perspective = False
        drawCam.Apply()
        drawView.Scale = keepScale
    Catch
        app.ScreenUpdating = wasUpdating
    End Try
    Try
        Dim restore As TransientGeometry = app.TransientGeometry
        live = modelView.Camera
        live.Eye = restore.CreatePoint(eyeX, eyeY, eyeZ)
        live.Target = restore.CreatePoint(targetX, targetY, targetZ)
        live.UpVector = restore.CreateUnitVector(upX, upY, upZ)
        live.Perspective = wasPerspective
        live.ApplyWithoutTransition()
    Catch
    End Try
    Try
        If returnView IsNot Nothing Then returnView.Activate()
    Catch
    End Try
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

Sub QuietUpdate(drawDoc As DrawingDocument)
    Try
        drawDoc.Update()
    Catch
    End Try
End Sub

Sub TryAddPartsList(sheet As Sheet, front As DrawingView, tg As TransientGeometry)
    Try
        Dim table As PartsList = sheet.PartsLists.Add(front, tg.CreatePoint2d(4.0, sheet.Height - 2.0))
        KeepPartsListOnSheet(sheet, table, tg)
    Catch
    End Try
End Sub

Sub KeepPartsListOnSheet(sheet As Sheet, table As PartsList, tg As TransientGeometry)
    Try
        Dim box As Box2d = table.RangeBox
        If box Is Nothing OrElse box.MinPoint Is Nothing OrElse box.MaxPoint Is Nothing Then Return
        Dim shiftX As Double = 0
        Dim shiftY As Double = 0
        If box.MinPoint.X < 1.4 Then shiftX = 1.4 - box.MinPoint.X
        If box.MaxPoint.X + shiftX > sheet.Width - 1.4 Then shiftX = sheet.Width - 1.4 - box.MaxPoint.X
        If box.MaxPoint.Y > sheet.Height - 1.2 Then shiftY = sheet.Height - 1.2 - box.MaxPoint.Y
        If box.MinPoint.Y + shiftY < 1.2 Then shiftY = 1.2 - box.MinPoint.Y
        If shiftX = 0 AndAlso shiftY = 0 Then Return
        Dim origin As Point2d = table.Position
        If origin Is Nothing Then Return
        table.Position = tg.CreatePoint2d(origin.X + shiftX, origin.Y + shiftY)
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
        Dim placed As Integer = 0
        Dim problem As String = ""
        Dim missed As New List(Of ComponentOccurrence)
        If views.ContainsKey("iso") Then
            problem = PlaceNearBalloons(sheet, views("iso"), targets, tg, placed, missed)
        Else
            For Each occ As ComponentOccurrence In targets
                missed.Add(occ)
            Next
        End If
        Dim pitch As Double = 1.6
        Dim nextY As New Dictionary(Of String, Double)
        Dim roles As New List(Of String)
        roles.Add("front")
        roles.Add("side")
        roles.Add("top")
        For Each occ As ComponentOccurrence In missed
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

Function BalloonPitch(sheet As Sheet, views As Dictionary(Of String, DrawingView), count As Integer) As Double
    Dim pitch As Double = 1.7
    If count < 2 Then Return pitch
    Dim room As Double = sheet.Height - 5.0
    If views.ContainsKey("iso") Then
        Dim beside As Double = views("iso").Height + 6.0
        If beside < room Then room = beside
    End If
    If room <= 0 Then Return pitch
    Dim needed As Double = pitch * (count - 1)
    If needed > room Then pitch = room / (count - 1)
    If pitch < 1.45 Then pitch = 1.45
    Return pitch
End Function

Function ColumnStart(sheet As Sheet, host As DrawingView, pitch As Double, count As Integer) As Double
    Dim span As Double = 0
    If count > 1 Then span = pitch * (count - 1)
    Dim startY As Double = host.Position.Y + span / 2
    Dim topLimit As Double = sheet.Height - 2.4
    Dim bottomLimit As Double = 2.4
    If startY > topLimit Then startY = topLimit
    If startY - span < bottomLimit Then startY = bottomLimit + span
    If startY > topLimit Then startY = topLimit
    Return startY
End Function

Function PlaceNearBalloons(sheet As Sheet, host As DrawingView, targets As List(Of ComponentOccurrence), tg As TransientGeometry, ByRef placed As Integer, missed As List(Of ComponentOccurrence)) As String
    Dim occs As New List(Of ComponentOccurrence)
    Dim tipX As New List(Of Double)
    Dim tipY As New List(Of Double)
    Dim problem As String = ""
    For Each occ As ComponentOccurrence In targets
        Dim edge As Point2d = OuterEdge(host, occ)
        If edge Is Nothing Then
            missed.Add(occ)
        Else
            Dim spot As Point2d = TipBeside(sheet, host, edge)
            occs.Add(occ)
            tipX.Add(spot.X)
            tipY.Add(spot.Y)
        End If
    Next
    NudgeApart(host, tipX, tipY, 1.35)
    Dim index As Integer = 0
    Do While index < occs.Count
        Dim note As String = PlaceOneNear(sheet, host, occs(index), tg, tipX(index), tipY(index))
        index = index + 1
        If note = "" Then
            placed = placed + 1
        Else
            problem = note
            missed.Add(occs(index - 1))
        End If
    Loop
    Return problem
End Function

Function PlaceSide(sheet As Sheet, host As DrawingView, occs As List(Of ComponentOccurrence), ys As List(Of Double), tg As TransientGeometry, onRight As Boolean, ByRef placed As Integer, missed As List(Of ComponentOccurrence), problem As String) As String
    Dim index As Integer = 0
    Do While index < occs.Count
        Dim tipX As Double = SideColumnX(sheet, host, onRight)
        Dim note As String = PlaceOneNear(sheet, host, occs(index), tg, tipX, ys(index))
        If note = "" Then
            placed = placed + 1
        Else
            problem = note
            missed.Add(occs(index))
        End If
        index = index + 1
    Loop
    Return problem
End Function

Function PlaceOneNear(sheet As Sheet, host As DrawingView, occ As ComponentOccurrence, tg As TransientGeometry, tipX As Double, tipY As Double) As String
    Dim curves As List(Of DrawingCurve) = CurvesForPart(host, occ)
    Dim tip As Point2d = tg.CreatePoint2d(tipX, tipY)
    Dim order As List(Of Integer) = NearCurveOrder(curves, tip, host)
    Dim lastProblem As String = "No part curve was available to attach."
    Dim index As Integer = 0
    Do While index < order.Count
        Dim failure As String = PlaceBalloon(sheet, curves(order(index)), tip)
        index = index + 1
        If failure = "" Then Return ""
        lastProblem = failure
    Loop
    Return lastProblem
End Function

Function OuterEdge(host As DrawingView, occ As ComponentOccurrence) As Point2d
    Dim curves As List(Of DrawingCurve) = CurvesForPart(host, occ)
    Dim best As Point2d = Nothing
    Dim bestScore As Double = -1
    Dim cx As Double = 0
    Dim cy As Double = 0
    If host.Position IsNot Nothing Then
        cx = host.Position.X
        cy = host.Position.Y
    End If
    Dim index As Integer = 0
    Dim span As Integer = curves.Count
    If span > 60 Then span = 60
    Do While index < span
        Dim mid As Point2d = PointOnCurve(curves(index))
        index = index + 1
        If mid Is Nothing Then Continue Do
        Dim dx As Double = mid.X - cx
        Dim dy As Double = mid.Y - cy
        Dim score As Double = dx * dx + dy * dy
        If score > bestScore Then
            bestScore = score
            best = mid
        End If
    Loop
    Return best
End Function

Function TipBeside(sheet As Sheet, host As DrawingView, edge As Point2d) As Point2d
    Dim cx As Double = edge.X
    Dim cy As Double = edge.Y
    If host.Position IsNot Nothing Then
        cx = host.Position.X
        cy = host.Position.Y
    End If
    Dim dx As Double = edge.X - cx
    Dim dy As Double = edge.Y - cy
    Dim ax As Double = Math.Abs(dx)
    Dim ay As Double = Math.Abs(dy)
    Dim span As Double = ax
    If ay > span Then span = ay
    If span < 0.05 Then span = 0.05
    Dim reach As Double = 1.15
    Dim tipX As Double = edge.X + dx / span * reach
    Dim tipY As Double = edge.Y + dy / span * reach
    Dim margin As Double = 1.2
    If tipX < margin Then tipX = margin
    If tipY < margin Then tipY = margin
    If tipX > sheet.Width - margin Then tipX = sheet.Width - margin
    If tipY > sheet.Height - margin Then tipY = sheet.Height - margin
    Return ThisApplication.TransientGeometry.CreatePoint2d(tipX, tipY)
End Function

Sub NudgeApart(host As DrawingView, xs As List(Of Double), ys As List(Of Double), gap As Double)
    If host Is Nothing OrElse host.Position Is Nothing Then Return
    Dim guard As Integer = 0
    Do While guard < 6
        guard = guard + 1
        Dim moved As Boolean = False
        Dim i As Integer = 0
        Do While i < xs.Count
            Dim j As Integer = i + 1
            Do While j < xs.Count
                Dim dx As Double = xs(j) - xs(i)
                Dim dy As Double = ys(j) - ys(i)
                If dx * dx + dy * dy < gap * gap Then
                    Dim ox As Double = xs(j) - host.Position.X
                    Dim oy As Double = ys(j) - host.Position.Y
                    Dim ax As Double = Math.Abs(ox)
                    Dim ay As Double = Math.Abs(oy)
                    Dim scale As Double = ax
                    If ay > scale Then scale = ay
                    If scale < 0.05 Then scale = 0.05
                    xs(j) = xs(j) + ox / scale * 0.45
                    ys(j) = ys(j) + oy / scale * 0.45
                    moved = True
                End If
                j = j + 1
            Loop
            i = i + 1
        Loop
        If Not moved Then Exit Do
    Loop
End Sub

Function PartAnchor(host As DrawingView, occ As ComponentOccurrence) As Point2d
    Dim curves As List(Of DrawingCurve) = CurvesForPart(host, occ)
    Dim sumX As Double = 0
    Dim sumY As Double = 0
    Dim count As Integer = 0
    Dim index As Integer = 0
    Dim span As Integer = curves.Count
    If span > 40 Then span = 40
    Do While index < span
        Dim mid As Point2d = PointOnCurve(curves(index))
        index = index + 1
        If mid Is Nothing Then Continue Do
        sumX = sumX + mid.X
        sumY = sumY + mid.Y
        count = count + 1
    Loop
    If count = 0 Then Return Nothing
    Return ThisApplication.TransientGeometry.CreatePoint2d(sumX / count, sumY / count)
End Function

Function SideColumnX(sheet As Sheet, host As DrawingView, onRight As Boolean) As Double
    Dim clearance As Double = 2.0
    Dim margin As Double = 1.6
    Dim columnX As Double
    If onRight Then
        columnX = host.Position.X + host.Width / 2 + clearance
        If columnX > sheet.Width - margin Then columnX = sheet.Width - margin
    Else
        columnX = host.Position.X - host.Width / 2 - clearance
        If columnX < margin Then columnX = margin
    End If
    Return columnX
End Function

Sub SpreadYs(ys As List(Of Double), pitch As Double, low As Double, high As Double)
    If ys.Count = 0 Then Return
    Dim order As New List(Of Integer)
    Dim i As Integer = 0
    Do While i < ys.Count
        order.Add(i)
        i = i + 1
    Loop
    Dim a As Integer = 0
    Do While a < order.Count
        Dim b As Integer = a + 1
        Do While b < order.Count
            If ys(order(b)) > ys(order(a)) Then
                Dim swap As Integer = order(a)
                order(a) = order(b)
                order(b) = swap
            End If
            b = b + 1
        Loop
        a = a + 1
    Loop
    Dim placed As New List(Of Double)
    a = 0
    Do While a < order.Count
        Dim y As Double = ys(order(a))
        If y > high Then y = high
        If y < low Then y = low
        If placed.Count > 0 Then
            Dim above As Double = placed(placed.Count - 1)
            If y > above - pitch Then y = above - pitch
        End If
        placed.Add(y)
        ys(order(a)) = y
        a = a + 1
    Loop
    Dim lowest As Double = ys(order(order.Count - 1))
    If lowest < low Then
        Dim lift As Double = low - lowest
        a = 0
        Do While a < ys.Count
            ys(a) = ys(a) + lift
            If ys(a) > high Then ys(a) = high
            a = a + 1
        Loop
    End If
End Sub

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
        Dim tip As Point2d = BalloonTip(sheet, host, role, nextY, tg)
        Dim order As List(Of Integer) = NearCurveOrder(curves, tip, host)
        Dim index As Integer = 0
        Do While index < order.Count
            Dim curve As DrawingCurve = curves(order(index))
            index = index + 1
            Dim failure As String = PlaceBalloon(sheet, curve, tip)
            If failure = "" Then
                If Not nextY.ContainsKey(role) Then nextY(role) = tip.Y
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
    Dim tipX As Double = BalloonColumnX(sheet, host)
    Dim tipY As Double = host.Position.Y
    If nextY.ContainsKey(role) Then tipY = nextY(role)
    Return tg.CreatePoint2d(tipX, tipY)
End Function

Function BalloonColumnX(sheet As Sheet, host As DrawingView) As Double
    Dim clearance As Double = 3.6
    Dim margin As Double = 2.4
    Dim rightX As Double = host.Position.X + host.Width / 2 + clearance
    If rightX <= sheet.Width - margin Then Return rightX
    Dim leftX As Double = host.Position.X - host.Width / 2 - clearance
    If leftX >= margin Then Return leftX
    Return sheet.Width - margin
End Function

Function NearCurveOrder(curves As List(Of DrawingCurve), tip As Point2d, host As DrawingView) As List(Of Integer)
    Dim order As New List(Of Integer)
    Dim used As New List(Of Integer)
    Dim span As Integer = curves.Count
    If span > 80 Then span = 80
    Dim picks As Integer = 0
    Do While picks < 8
        Dim best As Integer = -1
        Dim bestScore As Double = 1.0E+30
        Dim index As Integer = 0
        Do While index < span
            If Not used.Contains(index) Then
                Dim mid As Point2d = PointOnCurve(curves(index))
                If mid IsNot Nothing Then
                    Dim dx As Double = mid.X - tip.X
                    Dim dy As Double = mid.Y - tip.Y
                    Dim score As Double = dx * dx + dy * dy
                    If host IsNot Nothing AndAlso host.Position IsNot Nothing Then
                        Dim toward As Double = tip.X - host.Position.X
                        Dim edgeSide As Double = mid.X - host.Position.X
                        If toward * edgeSide < 0 Then score = score + host.Width * host.Width
                    End If
                    If score < bestScore Then
                        bestScore = score
                        best = index
                    End If
                End If
            End If
            index = index + 1
        Loop
        If best < 0 Then Exit Do
        used.Add(best)
        order.Add(best)
        picks = picks + 1
    Loop
    Return order
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
    Dim ax As Double = Math.Abs(dx)
    Dim ay As Double = Math.Abs(dy)
    Dim span As Double = ax
    If ay > span Then span = ay
    ' A bend only when the balloon is far enough from the edge to leave a real gap.
    If span < 0.9 Then Return Nothing
    Dim pull As Double = 0.45 / span
    If pull > 0.4 Then pull = 0.4
    Return ThisApplication.TransientGeometry.CreatePoint2d(tip.X + dx * pull, tip.Y + dy * pull)
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
            Dim rimPoint As Point2d = Nothing
            Try
                center = curve.CenterPoint
            Catch
                center = Nothing
            End Try
            Try
                rimPoint = curve.StartPoint
            Catch
                rimPoint = Nothing
            End Try
            If center IsNot Nothing AndAlso rimPoint IsNot Nothing Then
                Dim radius As Double = center.DistanceTo(rimPoint)
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

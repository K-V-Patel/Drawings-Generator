' CreateDrawing.vb
' iLogic rule. Run it from an open part (.ipt) or assembly (.iam).
'
' Creates a drawing from TemplateName, so the border, title block, and
' dimension style are the Inventor template. The front view follows the
' model ViewCube. Top and side are projected from that front view so they
' stay aligned. The isometric view uses the model Home view. The parts
' list stays in the top-left. Front, top, and side fill the space below
' it, and the isometric view fills the right side, at the largest scale
' that fits. Overall dimensions are added on the orthographic views.
' An assembly parts list sits in the top-left corner. Item, quantity,
' and part number columns are sized to their text. When the assembly has
' more than one part, each part gets one balloon just outside that part
' on the isometric view. Balloons that already fall in a row or a column
' share that line. Item numbers are not stacked in order.
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
        ' 1/50 keeps a large assembly big enough that each balloon can sit on its own part.
        ' The conservative fit was leaving the gantry at 1/100.
        If front.Scale < 0.02 Then front.Scale = 0.02
        QuietUpdate(drawDoc)

        Dim views As New Dictionary(Of String, DrawingView)
        views("front") = front
        views("top") = sheet.DrawingViews.AddProjectedView(front, tg.CreatePoint2d(front.Position.X, front.Position.Y + front.Height), style)
        views("side") = sheet.DrawingViews.AddProjectedView(front, tg.CreatePoint2d(front.Position.X + front.Width, front.Position.Y), style)
        views("iso") = sheet.DrawingViews.AddBaseView( _
            model, tg.CreatePoint2d(sheet.Width * 0.75, sheet.Height * 0.68), _
            front.Scale, ViewOrientationTypeEnum.kIsoTopRightViewOrientation, style)
        ApplyHomeCamera(views("iso"), model)
        QuietUpdate(drawDoc)
        If model.DocumentType = DocumentTypeEnum.kAssemblyDocumentObject Then
            ShowAssemblyParts(sheet, views)
            TryAddPartsList(drawDoc, sheet, views("front"), tg)
        End If
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
    Dim topView As DrawingView = views("top")
    Dim side As DrawingView = views("side")
    Dim iso As DrawingView = views("iso")
    iso.Scale = front.Scale
    Dim gap As Double = 2.6
    Dim oL As Double = 0
    Dim oB As Double = 0
    Dim oR As Double = 0
    Dim oT As Double = 0
    Dim iL As Double = 0
    Dim iB As Double = 0
    Dim iR As Double = 0
    Dim iT As Double = 0
    ZoneFrame(sheet, oL, oB, oR, oT, iL, iB, iR, iT)
    Dim orthoW As Double = front.Width + gap + side.Width
    Dim orthoH As Double = front.Height + gap + topView.Height
    Dim placeLeft As Double = oL + ((oR - oL) - orthoW) / 2
    Dim placeBottom As Double = oB + ((oT - oB) - orthoH) / 2
    If placeLeft < oL Then placeLeft = oL
    If placeBottom < oB Then placeBottom = oB
    Dim frontX As Double = placeLeft + front.Width / 2
    Dim frontY As Double = placeBottom + front.Height / 2
    Dim sideX As Double = placeLeft + front.Width + gap + side.Width / 2
    Dim sideY As Double = frontY
    Dim topX As Double = frontX
    Dim topY As Double = frontY + front.Height / 2 + gap + topView.Height / 2
    TryMove(front, tg.CreatePoint2d(frontX, frontY))
    TryMove(topView, tg.CreatePoint2d(topX, topY))
    TryMove(side, tg.CreatePoint2d(sideX, sideY))
    Dim isoX As Double = (iL + iR) / 2
    Dim isoY As Double = (iB + iT) / 2
    If isoX - iso.Width / 2 < iL Then isoX = iL + iso.Width / 2
    If isoX + iso.Width / 2 > iR Then isoX = iR - iso.Width / 2
    If isoY - iso.Height / 2 < iB Then isoY = iB + iso.Height / 2
    If isoY + iso.Height / 2 > iT Then isoY = iT - iso.Height / 2
    TryMove(iso, tg.CreatePoint2d(isoX, isoY))
End Sub

Sub TryMove(view As DrawingView, point As Point2d)
    Try
        view.Position = point
    Catch
    End Try
End Sub

Sub ShrinkToSheet(drawDoc As DrawingDocument, sheet As Sheet, views As Dictionary(Of String, DrawingView), tg As TransientGeometry)
    QuietUpdate(drawDoc)
    views("front").Scale = LargestZoneScale(sheet, views)
    views("iso").Scale = views("front").Scale
    Dim pass As Integer = 1
    Do While pass <= 4
        QuietUpdate(drawDoc)
        PositionViews(sheet, views, tg)
        QuietUpdate(drawDoc)
        If LayoutPressure(sheet, views) <= 1.05 Then Exit Do
        views("front").Scale = NextSmallerScale(views("front").Scale)
        views("iso").Scale = views("front").Scale
        pass = pass + 1
    Loop
    QuietUpdate(drawDoc)
    PositionViews(sheet, views, tg)
    QuietUpdate(drawDoc)
    Try
        If sheet.PartsLists.Count > 0 Then SeatPartsList(sheet, sheet.PartsLists.Item(1), tg)
    Catch
    End Try
End Sub

Sub ZoneFrame(sheet As Sheet, ByRef oL As Double, ByRef oB As Double, ByRef oR As Double, ByRef oT As Double, ByRef iL As Double, ByRef iB As Double, ByRef iR As Double, ByRef iT As Double)
    Dim leftLimit As Double = 0
    Dim bottomLimit As Double = 0
    Dim rightLimit As Double = 0
    Dim topLimit As Double = 0
    BorderLimits(sheet, leftLimit, bottomLimit, rightLimit, topLimit)
    Dim pad As Double = 1.4
    Dim leftEdge As Double = leftLimit + pad
    Dim bottomEdge As Double = bottomLimit + pad
    Dim rightEdge As Double = rightLimit - pad
    Dim topEdge As Double = topLimit - pad
    Dim listL As Double = 0
    Dim listB As Double = 0
    Dim listR As Double = 0
    Dim listT As Double = 0
    Dim hasList As Boolean = False
    Dim titleL As Double = 0
    Dim titleB As Double = 0
    Dim titleR As Double = 0
    Dim titleT As Double = 0
    Dim hasTitle As Boolean = False
    ReadOccupied(sheet, listL, listB, listR, listT, hasList, titleL, titleB, titleR, titleT, hasTitle)
    Dim innerW As Double = rightEdge - leftEdge
    If innerW < 8 Then innerW = 8
    Dim split As Double = leftEdge + innerW * 0.56
    If hasList AndAlso listR + 1.0 > split Then split = listR + 1.0
    If split > leftEdge + innerW * 0.7 Then split = leftEdge + innerW * 0.7
    If split < leftEdge + 4 Then split = leftEdge + innerW * 0.5
    oL = leftEdge
    oR = split - 0.7
    iL = split + 0.7
    iR = rightEdge
    oB = bottomEdge
    iB = bottomEdge
    oT = topEdge
    iT = topEdge
    If hasList AndAlso listB - 0.8 < oT Then oT = listB - 0.8
    If hasList AndAlso listR > iL - 0.2 AndAlso listB - 0.8 < iT Then iT = listB - 0.8
    If hasTitle Then
        If titleR > oL AndAlso titleL < oR AndAlso titleT + 0.5 > oB Then oB = titleT + 0.5
        If titleR > iL AndAlso titleL < iR AndAlso titleT + 0.5 > iB Then iB = titleT + 0.5
    End If
    If oT - oB < 3 OrElse oR - oL < 3 Then
        Dim stackL As Double = leftEdge
        If hasList AndAlso listR + 0.8 > stackL Then stackL = listR + 0.8
        Dim stackB As Double = bottomEdge
        Dim stackT As Double = topEdge
        If hasTitle AndAlso titleL < rightEdge AndAlso titleT + 0.5 > stackB Then stackB = titleT + 0.5
        Dim mid As Double = (stackB + stackT) / 2
        iL = stackL
        iR = rightEdge
        iT = stackT
        iB = mid + 0.4
        oL = stackL
        oR = rightEdge
        oT = mid - 0.4
        oB = stackB
    End If
End Sub

Function LargestZoneScale(sheet As Sheet, views As Dictionary(Of String, DrawingView)) As Double
    Dim frontW As Double = SpanW(views("front"))
    Dim frontH As Double = SpanH(views("front"))
    Dim topH As Double = SpanH(views("top"))
    Dim sideW As Double = SpanW(views("side"))
    Dim isoW As Double = SpanW(views("iso"))
    Dim isoH As Double = SpanH(views("iso"))
    Dim oL As Double = 0
    Dim oB As Double = 0
    Dim oR As Double = 0
    Dim oT As Double = 0
    Dim iL As Double = 0
    Dim iB As Double = 0
    Dim iR As Double = 0
    Dim iT As Double = 0
    ZoneFrame(sheet, oL, oB, oR, oT, iL, iB, iR, iT)
    Dim gap As Double = 2.6
    Dim availOW As Double = oR - oL
    Dim availOH As Double = oT - oB
    Dim availIW As Double = iR - iL
    Dim availIH As Double = iT - iB
    If availOW < 3 Then availOW = 3
    If availOH < 3 Then availOH = 3
    If availIW < 3 Then availIW = 3
    If availIH < 3 Then availIH = 3
    Dim sOrthoW As Double = (availOW - gap) / Math.Max(frontW + sideW, 0.1)
    Dim sOrthoH As Double = (availOH - gap) / Math.Max(frontH + topH, 0.1)
    Dim sIsoW As Double = (availIW - 1.8) / Math.Max(isoW, 0.1)
    Dim sIsoH As Double = (availIH - 1.8) / Math.Max(isoH, 0.1)
    Dim s As Double = sOrthoW
    If sOrthoH < s Then s = sOrthoH
    If sIsoW < s Then s = sIsoW
    If sIsoH < s Then s = sIsoH
    s = s * 0.94
    If s < 0.005 Then s = 0.005
    Return NiceScale(s)
End Function

Function SpanW(view As DrawingView) As Double
    If view Is Nothing Then Return 1
    Return view.Width / Math.Max(view.Scale, 0.0001)
End Function

Function SpanH(view As DrawingView) As Double
    If view Is Nothing Then Return 1
    Return view.Height / Math.Max(view.Scale, 0.0001)
End Function

Function NextSmallerScale(current As Double) As Double
    Dim choices() As Double = {2, 1, 0.5, 0.25, 0.2, 0.1, 1.0 / 12, 1.0 / 16, 0.05, 1.0 / 20, 1.0 / 24, 1.0 / 30, 1.0 / 32, 0.025, 0.02, 1.0 / 48, 1.0 / 50, 1.0 / 64, 0.01, 0.005}
    For Each choice As Double In choices
        If choice < current * 0.98 Then Return choice
    Next
    Return 0.005
End Function

Sub BorderLimits(sheet As Sheet, ByRef leftLimit As Double, ByRef bottomLimit As Double, ByRef rightLimit As Double, ByRef topLimit As Double)
    leftLimit = 1.6
    bottomLimit = 1.6
    rightLimit = sheet.Width - 1.6
    topLimit = sheet.Height - 1.4
    Try
        If sheet.Border Is Nothing OrElse sheet.Border.RangeBox Is Nothing Then Return
        Dim box As Box2d = sheet.Border.RangeBox
        If box.MinPoint Is Nothing OrElse box.MaxPoint Is Nothing Then Return
        leftLimit = box.MinPoint.X + 0.35
        bottomLimit = box.MinPoint.Y + 0.35
        rightLimit = box.MaxPoint.X - 0.35
        topLimit = box.MaxPoint.Y - 0.3
    Catch
    End Try
End Sub

Sub ReadOccupied(sheet As Sheet, ByRef listL As Double, ByRef listB As Double, ByRef listR As Double, ByRef listT As Double, ByRef hasList As Boolean, ByRef titleL As Double, ByRef titleB As Double, ByRef titleR As Double, ByRef titleT As Double, ByRef hasTitle As Boolean)
    hasList = False
    hasTitle = False
    listL = 0
    listB = 0
    listR = 0
    listT = 0
    titleL = 0
    titleB = 0
    titleR = 0
    titleT = 0
    Try
        If sheet.PartsLists.Count > 0 Then
            Dim listBox As Box2d = sheet.PartsLists.Item(1).RangeBox
            If listBox IsNot Nothing AndAlso listBox.MinPoint IsNot Nothing AndAlso listBox.MaxPoint IsNot Nothing Then
                listL = listBox.MinPoint.X
                listB = listBox.MinPoint.Y
                listR = listBox.MaxPoint.X
                listT = listBox.MaxPoint.Y
                hasList = True
            End If
        End If
    Catch
    End Try
    Try
        If sheet.TitleBlock IsNot Nothing Then
            Dim titleBox As Box2d = sheet.TitleBlock.RangeBox
            If titleBox IsNot Nothing AndAlso titleBox.MinPoint IsNot Nothing AndAlso titleBox.MaxPoint IsNot Nothing Then
                titleL = titleBox.MinPoint.X
                titleB = titleBox.MinPoint.Y
                titleR = titleBox.MaxPoint.X
                titleT = titleBox.MaxPoint.Y
                Dim titleArea As Double = (titleR - titleL) * (titleT - titleB)
                Dim sheetArea As Double = sheet.Width * sheet.Height
                If titleArea > 0 AndAlso titleArea < sheetArea * 0.35 Then hasTitle = True
            End If
        End If
    Catch
    End Try
End Sub

Function LayoutPressure(sheet As Sheet, views As Dictionary(Of String, DrawingView)) As Double
    Dim factor As Double = 1.0
    Dim leftLimit As Double = 0
    Dim bottomLimit As Double = 0
    Dim rightLimit As Double = 0
    Dim topLimit As Double = 0
    BorderLimits(sheet, leftLimit, bottomLimit, rightLimit, topLimit)
    Dim viewPad As Double = 0.8
    Dim leftEdge As Double = leftLimit + viewPad
    Dim bottomEdge As Double = bottomLimit + viewPad
    Dim rightEdge As Double = rightLimit - viewPad
    Dim topEdge As Double = topLimit - viewPad
    Dim listL As Double = 0
    Dim listB As Double = 0
    Dim listR As Double = 0
    Dim listT As Double = 0
    Dim hasList As Boolean = False
    Dim titleL As Double = 0
    Dim titleB As Double = 0
    Dim titleR As Double = 0
    Dim titleT As Double = 0
    Dim hasTitle As Boolean = False
    ReadOccupied(sheet, listL, listB, listR, listT, hasList, titleL, titleB, titleR, titleT, hasTitle)
    Dim names As New List(Of String)
    names.Add("front")
    names.Add("top")
    names.Add("side")
    names.Add("iso")
    Dim i As Integer = 0
    Do While i < names.Count
        Dim view As DrawingView = views(names(i))
        If view IsNot Nothing AndAlso view.Position IsNot Nothing Then
            Dim left As Double = view.Position.X - view.Width / 2
            Dim right As Double = view.Position.X + view.Width / 2
            Dim low As Double = view.Position.Y - view.Height / 2
            Dim high As Double = view.Position.Y + view.Height / 2
            If left < leftEdge Then factor = Math.Max(factor, view.Width / Math.Max(view.Width - (leftEdge - left), 0.5))
            If right > rightEdge Then factor = Math.Max(factor, view.Width / Math.Max(view.Width - (right - rightEdge), 0.5))
            If low < bottomEdge Then factor = Math.Max(factor, view.Height / Math.Max(view.Height - (bottomEdge - low), 0.5))
            If high > topEdge Then factor = Math.Max(factor, view.Height / Math.Max(view.Height - (high - topEdge), 0.5))
            If hasList AndAlso RangesHit(left, low, right, high, listL, listB, listR, listT, 0.4) Then factor = Math.Max(factor, 1.18)
            If hasTitle AndAlso RangesHit(left, low, right, high, titleL, titleB, titleR, titleT, 0.4) Then factor = Math.Max(factor, 1.18)
        End If
        Dim j As Integer = i + 1
        Do While j < names.Count
            factor = Math.Max(factor, PairPressure(views(names(i)), views(names(j))))
            j = j + 1
        Loop
        i = i + 1
    Loop
    If factor > 1.8 Then factor = 1.8
    Return factor
End Function

Function PairPressure(a As DrawingView, b As DrawingView) As Double
    If a Is Nothing OrElse b Is Nothing Then Return 1.0
    If a.Position Is Nothing OrElse b.Position Is Nothing Then Return 1.0
    Dim pad As Double = 1.1
    Dim aL As Double = a.Position.X - a.Width / 2 - pad
    Dim aR As Double = a.Position.X + a.Width / 2 + pad
    Dim aB As Double = a.Position.Y - a.Height / 2 - pad
    Dim aT As Double = a.Position.Y + a.Height / 2 + pad
    Dim bL As Double = b.Position.X - b.Width / 2
    Dim bR As Double = b.Position.X + b.Width / 2
    Dim bB As Double = b.Position.Y - b.Height / 2
    Dim bT As Double = b.Position.Y + b.Height / 2
    If RangesHit(aL, aB, aR, aT, bL, bB, bR, bT, 0) Then Return 1.18
    Return 1.0
End Function

Function RangesHit(aL As Double, aB As Double, aR As Double, aT As Double, bL As Double, bB As Double, bR As Double, bT As Double, pad As Double) As Boolean
    If aL > bR + pad Then Return False
    If aR < bL - pad Then Return False
    If aB > bT + pad Then Return False
    If aT < bB - pad Then Return False
    Return True
End Function

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
            textPoint = tg.CreatePoint2d((minValue + maxValue) / 2, view.Position.Y - view.Height / 2 - 1.8)
            kind = DimensionTypeEnum.kHorizontalDimensionType
        Else
            textPoint = tg.CreatePoint2d(view.Position.X - view.Width / 2 - 1.6, (minValue + maxValue) / 2)
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

Sub TryAddPartsList(drawDoc As DrawingDocument, sheet As Sheet, front As DrawingView, tg As TransientGeometry)
    Try
        Dim leftLimit As Double = 0
        Dim bottomLimit As Double = 0
        Dim rightLimit As Double = 0
        Dim topLimit As Double = 0
        BorderLimits(sheet, leftLimit, bottomLimit, rightLimit, topLimit)
        Dim table As PartsList = sheet.PartsLists.Add(front, tg.CreatePoint2d(leftLimit, topLimit))
        QuietUpdate(drawDoc)
        FitPartsListColumns(table)
        QuietUpdate(drawDoc)
        ShrinkWideColumns(sheet, table)
        QuietUpdate(drawDoc)
        SeatPartsList(sheet, table, tg)
    Catch
    End Try
End Sub

Sub FitPartsListColumns(table As PartsList)
    Dim colIndex As Integer = 1
    Do While colIndex <= table.PartsListColumns.Count
        Dim col As PartsListColumn = table.PartsListColumns.Item(colIndex)
        Dim kind As Integer = ColumnKind(col)
        If kind <> 0 Then
            Dim chars As Integer = WidestColumnText(table, col, colIndex)
            Dim width As Double = chars * 0.22 + 0.55
            If kind = 1 OrElse kind = 2 Then
                If width < 1.15 Then width = 1.15
                If width > 2.6 Then width = 2.6
            Else
                If width < 2.2 Then width = 2.2
                If width > 10.0 Then width = 10.0
            End If
            Try
                col.Width = width
            Catch
            End Try
        End If
        colIndex = colIndex + 1
    Loop
End Sub

Function ColumnKind(col As PartsListColumn) As Integer
    ' PropertyTypeEnum has no parts-list members, so the heading text decides the column.
    Dim title As String = ""
    Try
        If col.Title IsNot Nothing Then title = col.Title.ToUpper()
    Catch
        title = ""
    End Try
    If title.Contains("QTY") OrElse title.Contains("QUANTITY") Then Return 2
    If title.Contains("ITEM") Then Return 1
    If title.Contains("PART") AndAlso title.Contains("NUMBER") Then Return 3
    If title.Contains("PART NO") Then Return 3
    Return 0
End Function

Function WidestColumnText(table As PartsList, col As PartsListColumn, colIndex As Integer) As Integer
    Dim widest As Integer = 0
    Try
        Dim heading As Integer = LongestPiece(col.Title)
        If heading > widest Then widest = heading
    Catch
    End Try
    Dim rowIndex As Integer = 1
    Do While rowIndex <= table.PartsListRows.Count
        Try
            Dim cellText As String = table.PartsListRows.Item(rowIndex).Item(colIndex).Value
            Dim piece As Integer = LongestPiece(cellText)
            If piece > widest Then widest = piece
        Catch
        End Try
        rowIndex = rowIndex + 1
    Loop
    Return widest
End Function

Function LongestPiece(text As String) As Integer
    If text Is Nothing OrElse text = "" Then Return 0
    Dim longest As Integer = 0
    Dim current As Integer = 0
    Dim index As Integer = 1
    Do While index <= text.Length
        Dim ch As String = Mid(text, index, 1)
        If ch = Chr(10) OrElse ch = Chr(13) Then
            If current > longest Then longest = current
            current = 0
        Else
            current = current + 1
        End If
        index = index + 1
    Loop
    If current > longest Then longest = current
    Return longest
End Function

Sub ShrinkWideColumns(sheet As Sheet, table As PartsList)
    Try
        Dim box As Box2d = table.RangeBox
        If box Is Nothing OrElse box.MinPoint Is Nothing OrElse box.MaxPoint Is Nothing Then Return
        Dim leftLimit As Double = 0
        Dim bottomLimit As Double = 0
        Dim rightLimit As Double = 0
        Dim topLimit As Double = 0
        BorderLimits(sheet, leftLimit, bottomLimit, rightLimit, topLimit)
        Dim maxWidth As Double = rightLimit - leftLimit
        If maxWidth > sheet.Width * 0.42 Then maxWidth = sheet.Width * 0.42
        Dim tableWidth As Double = box.MaxPoint.X - box.MinPoint.X
        If tableWidth <= maxWidth Then Return
        Dim overflow As Double = tableWidth - maxWidth
        Dim widest As PartsListColumn = Nothing
        Dim widestW As Double = 0
        Dim colIndex As Integer = 1
        Do While colIndex <= table.PartsListColumns.Count
            Dim col As PartsListColumn = table.PartsListColumns.Item(colIndex)
            If ColumnKind(col) = 0 AndAlso col.Width > widestW Then
                widest = col
                widestW = col.Width
            End If
            colIndex = colIndex + 1
        Loop
        If widest Is Nothing Then Return
        Dim fitted As Double = widest.Width - overflow - 0.15
        If fitted < 3.2 Then fitted = 3.2
        widest.Width = fitted
    Catch
    End Try
End Sub

Sub SeatPartsList(sheet As Sheet, table As PartsList, tg As TransientGeometry)
    Try
        Dim box As Box2d = table.RangeBox
        If box Is Nothing OrElse box.MinPoint Is Nothing OrElse box.MaxPoint Is Nothing Then Return
        Dim leftLimit As Double = 0
        Dim bottomLimit As Double = 0
        Dim rightLimit As Double = 0
        Dim topLimit As Double = 0
        BorderLimits(sheet, leftLimit, bottomLimit, rightLimit, topLimit)
        Dim origin As Point2d = table.Position
        If origin Is Nothing Then Return
        Dim shiftX As Double = leftLimit - box.MinPoint.X
        Dim shiftY As Double = topLimit - box.MaxPoint.Y
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
        Dim minX As Double = 0
        Dim minY As Double = 0
        Dim maxX As Double = 0
        Dim maxY As Double = 0
        If Not PartExtent(host, occ, minX, minY, maxX, maxY) Then
            missed.Add(occ)
        Else
            Dim spot As Point2d = TipOutside(sheet, host, minX, minY, maxX, maxY)
            occs.Add(occ)
            tipX.Add(spot.X)
            tipY.Add(spot.Y)
        End If
    Next
    AlignNearby(host, tipX, tipY)
    KeepTipsClear(sheet, host, tipX, tipY)
    ClampTips(sheet, tipX, tipY)
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

Function PartExtent(host As DrawingView, occ As ComponentOccurrence, ByRef minX As Double, ByRef minY As Double, ByRef maxX As Double, ByRef maxY As Double) As Boolean
    minX = 0
    minY = 0
    maxX = 0
    maxY = 0
    Dim seen As Integer = 0
    Dim curves As List(Of DrawingCurve) = CurvesForPart(host, occ)
    Dim index As Integer = 0
    Dim limit As Integer = curves.Count
    If limit > 160 Then limit = 160
    Do While index < limit
        IncludeCurveExtent(curves(index), minX, minY, maxX, maxY, seen)
        index = index + 1
    Loop
    If seen = 0 Then Return False
    Return True
End Function

Sub IncludeCurveExtent(curve As DrawingCurve, ByRef minX As Double, ByRef minY As Double, ByRef maxX As Double, ByRef maxY As Double, ByRef seen As Integer)
    Try
        IncludePoint(curve.MidPoint, minX, minY, maxX, maxY, seen)
    Catch
    End Try
    Try
        IncludePoint(curve.StartPoint, minX, minY, maxX, maxY, seen)
    Catch
    End Try
    Try
        IncludePoint(curve.EndPoint, minX, minY, maxX, maxY, seen)
    Catch
    End Try
End Sub

Sub IncludePoint(pt As Point2d, ByRef minX As Double, ByRef minY As Double, ByRef maxX As Double, ByRef maxY As Double, ByRef seen As Integer)
    If pt Is Nothing Then Return
    If seen = 0 Then
        minX = pt.X
        minY = pt.Y
        maxX = pt.X
        maxY = pt.Y
    Else
        If pt.X < minX Then minX = pt.X
        If pt.Y < minY Then minY = pt.Y
        If pt.X > maxX Then maxX = pt.X
        If pt.Y > maxY Then maxY = pt.Y
    End If
    seen = seen + 1
End Sub

Function TipOutside(sheet As Sheet, host As DrawingView, minX As Double, minY As Double, maxX As Double, maxY As Double) As Point2d
    Dim px As Double = (minX + maxX) / 2
    Dim py As Double = (minY + maxY) / 2
    Dim vx As Double = px
    Dim vy As Double = py
    If host IsNot Nothing AndAlso host.Position IsNot Nothing Then
        vx = host.Position.X
        vy = host.Position.Y
    End If
    Dim dx As Double = px - vx
    Dim dy As Double = py - vy
    Dim reach As Double = 0.55
    Dim tipX As Double = px
    Dim tipY As Double = py
    If Math.Abs(dx) >= Math.Abs(dy) Then
        If dx >= 0 Then
            tipX = maxX + reach
        Else
            tipX = minX - reach
        End If
        tipY = py
    Else
        If dy >= 0 Then
            tipY = maxY + reach
        Else
            tipY = minY - reach
        End If
        tipX = px
    End If
    Dim margin As Double = 1.15
    If tipX < margin Then tipX = margin
    If tipY < margin Then tipY = margin
    If tipX > sheet.Width - margin Then tipX = sheet.Width - margin
    If tipY > sheet.Height - margin Then tipY = sheet.Height - margin
    Return ThisApplication.TransientGeometry.CreatePoint2d(tipX, tipY)
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

Sub AlignNearby(host As DrawingView, xs As List(Of Double), ys As List(Of Double))
    If host Is Nothing OrElse host.Position Is Nothing Then Return
    If xs Is Nothing OrElse ys Is Nothing Then Return
    Dim count As Integer = xs.Count
    If ys.Count < count Then count = ys.Count
    If count < 2 Then Return
    Dim ox As New List(Of Double)
    Dim oy As New List(Of Double)
    Dim parent As New List(Of Integer)
    Dim mode As New List(Of Integer)
    Dim i As Integer = 0
    Do While i < count
        ox.Add(xs(i))
        oy.Add(ys(i))
        parent.Add(i)
        mode.Add(0)
        i = i + 1
    Loop
    Dim crossTol As Double = 2.6
    Dim alongTol As Double = 8.0
    Dim j As Integer = 0
    Dim dx As Double = 0
    Dim dy As Double = 0
    Dim match As Boolean = False
    i = 0
    Do While i < count
        Dim bestCol As Integer = -1
        Dim bestColCross As Double = crossTol
        Dim bestColAlong As Double = alongTol
        Dim bestRow As Integer = -1
        Dim bestRowCross As Double = crossTol
        Dim bestRowAlong As Double = alongTol
        j = 0
        Do While j < count
            If j <> i Then
                dx = Math.Abs(ox(j) - ox(i))
                dy = Math.Abs(oy(j) - oy(i))
                If dx <= crossTol AndAlso dy <= alongTol AndAlso dy >= dx Then
                    If dx < bestColCross - 0.001 OrElse (Math.Abs(dx - bestColCross) <= 0.001 AndAlso dy < bestColAlong) Then
                        bestCol = j
                        bestColCross = dx
                        bestColAlong = dy
                    End If
                End If
                If dy <= crossTol AndAlso dx <= alongTol AndAlso dx > dy Then
                    If dy < bestRowCross - 0.001 OrElse (Math.Abs(dy - bestRowCross) <= 0.001 AndAlso dx < bestRowAlong) Then
                        bestRow = j
                        bestRowCross = dy
                        bestRowAlong = dx
                    End If
                End If
            End If
            j = j + 1
        Loop
        If bestCol >= 0 AndAlso (bestRow < 0 OrElse bestColCross <= bestRowCross) Then
            mode(i) = 1
        ElseIf bestRow >= 0 Then
            mode(i) = 2
        End If
        i = i + 1
    Loop
    i = 0
    Do While i < count
        j = i + 1
        Do While j < count
            If mode(i) <> 0 AndAlso mode(i) = mode(j) Then
                dx = Math.Abs(ox(j) - ox(i))
                dy = Math.Abs(oy(j) - oy(i))
                match = False
                If mode(i) = 1 AndAlso dx <= crossTol AndAlso dy <= alongTol Then match = True
                If mode(i) = 2 AndAlso dy <= crossTol AndAlso dx <= alongTol Then match = True
                If match Then JoinTip(parent, i, j)
            End If
            j = j + 1
        Loop
        i = i + 1
    Loop
    Dim seenRoot As New List(Of Integer)
    i = 0
    Do While i < count
        Dim root As Integer = FindTip(parent, i)
        If Not seenRoot.Contains(root) Then
            seenRoot.Add(root)
            Dim members As New List(Of Integer)
            Dim k As Integer = 0
            Do While k < count
                If FindTip(parent, k) = root Then members.Add(k)
                k = k + 1
            Loop
            If members.Count > 1 AndAlso mode(i) <> 0 Then
                SnapLine(host, xs, ys, ox, oy, members, mode(i) = 1)
            End If
        End If
        i = i + 1
    Loop
    SettleLines(xs, ys, 1.35)
End Sub

Sub JoinTip(parent As List(Of Integer), a As Integer, b As Integer)
    Dim ra As Integer = FindTip(parent, a)
    Dim rb As Integer = FindTip(parent, b)
    If ra = rb Then Return
    parent(rb) = ra
End Sub

Function FindTip(parent As List(Of Integer), index As Integer) As Integer
    Dim guard As Integer = 0
    Do While parent(index) <> index
        parent(index) = parent(parent(index))
        index = parent(index)
        guard = guard + 1
        If guard > parent.Count + 2 Then Exit Do
    Loop
    Return index
End Function

Sub SnapLine(host As DrawingView, xs As List(Of Double), ys As List(Of Double), ox As List(Of Double), oy As List(Of Double), members As List(Of Integer), asColumn As Boolean)
    Dim center As Double = host.Position.X
    If Not asColumn Then center = host.Position.Y
    Dim cap As Double = 2.2
    Dim lo As Double = -1.0E+30
    Dim hi As Double = 1.0E+30
    Dim n As Integer = 0
    Dim origin As Double = 0
    Do While n < members.Count
        origin = oy(members(n))
        If asColumn Then origin = ox(members(n))
        If origin - cap > lo Then lo = origin - cap
        If origin + cap < hi Then hi = origin + cap
        n = n + 1
    Loop
    Dim share As Double = lo
    If lo <= hi Then
        If Math.Abs(lo - center) >= Math.Abs(hi - center) Then
            share = lo
        Else
            share = hi
        End If
    Else
        share = oy(members(0))
        If asColumn Then share = ox(members(0))
        n = 1
        Do While n < members.Count
            origin = oy(members(n))
            If asColumn Then origin = ox(members(n))
            If Math.Abs(origin - center) > Math.Abs(share - center) Then share = origin
            n = n + 1
        Loop
    End If
    n = 0
    Do While n < members.Count
        Dim id As Integer = members(n)
        If asColumn Then
            xs(id) = PullToward(ox(id), share, cap)
        Else
            ys(id) = PullToward(oy(id), share, cap)
        End If
        n = n + 1
    Loop
    SpaceMembers(xs, ys, ox, oy, members, asColumn, 1.35)
End Sub

Function PullToward(origin As Double, target As Double, cap As Double) As Double
    Dim delta As Double = target - origin
    If delta > cap Then Return origin + cap
    If delta < -cap Then Return origin - cap
    Return target
End Function

Sub SpaceMembers(xs As List(Of Double), ys As List(Of Double), ox As List(Of Double), oy As List(Of Double), members As List(Of Integer), asColumn As Boolean, gap As Double)
    Dim order As New List(Of Integer)
    Dim n As Integer = 0
    Do While n < members.Count
        order.Add(members(n))
        n = n + 1
    Loop
    Dim a As Integer = 0
    Do While a < order.Count
        Dim b As Integer = a + 1
        Do While b < order.Count
            Dim aPos As Double = xs(order(a))
            Dim bPos As Double = xs(order(b))
            If asColumn Then
                aPos = ys(order(a))
                bPos = ys(order(b))
            End If
            If bPos < aPos Then
                Dim swap As Integer = order(a)
                order(a) = order(b)
                order(b) = swap
            End If
            b = b + 1
        Loop
        a = a + 1
    Loop
    a = 1
    Do While a < order.Count
        Dim prev As Double = xs(order(a - 1))
        Dim cur As Double = xs(order(a))
        If asColumn Then
            prev = ys(order(a - 1))
            cur = ys(order(a))
        End If
        If cur < prev + gap Then cur = prev + gap
        If asColumn Then
            ys(order(a)) = cur
        Else
            xs(order(a)) = cur
        End If
        a = a + 1
    Loop
    Dim oldSum As Double = 0
    Dim newSum As Double = 0
    a = 0
    Do While a < order.Count
        If asColumn Then
            oldSum = oldSum + oy(order(a))
            newSum = newSum + ys(order(a))
        Else
            oldSum = oldSum + ox(order(a))
            newSum = newSum + xs(order(a))
        End If
        a = a + 1
    Loop
    Dim slide As Double = (oldSum - newSum) / order.Count
    a = 0
    Do While a < order.Count
        If asColumn Then
            ys(order(a)) = ys(order(a)) + slide
        Else
            xs(order(a)) = xs(order(a)) + slide
        End If
        a = a + 1
    Loop
End Sub

Sub SettleLines(xs As List(Of Double), ys As List(Of Double), gap As Double)
    If xs Is Nothing OrElse ys Is Nothing Then Return
    Dim guard As Integer = 0
    Do While guard < 6
        guard = guard + 1
        Dim moved As Boolean = False
        Dim i As Integer = 0
        Do While i < xs.Count
            Dim j As Integer = i + 1
            Do While j < xs.Count AndAlso j < ys.Count
                Dim dx As Double = xs(j) - xs(i)
                Dim dy As Double = ys(j) - ys(i)
                Dim ax As Double = Math.Abs(dx)
                Dim ay As Double = Math.Abs(dy)
                Dim push As Double = 0
                If ax < gap AndAlso ay < gap Then
                    If ax <= 0.2 Then
                        push = (gap - ay) / 2 + 0.05
                        If push < 0.12 Then push = 0.12
                        If dy >= 0 Then
                            ys(i) = ys(i) - push
                            ys(j) = ys(j) + push
                        Else
                            ys(i) = ys(i) + push
                            ys(j) = ys(j) - push
                        End If
                        moved = True
                    ElseIf ay <= 0.2 Then
                        push = (gap - ax) / 2 + 0.05
                        If push < 0.12 Then push = 0.12
                        If dx >= 0 Then
                            xs(i) = xs(i) - push
                            xs(j) = xs(j) + push
                        Else
                            xs(i) = xs(i) + push
                            xs(j) = xs(j) - push
                        End If
                        moved = True
                    End If
                End If
                j = j + 1
            Loop
            i = i + 1
        Loop
        If Not moved Then Exit Do
    Loop
End Sub

Sub NudgeApart(host As DrawingView, xs As List(Of Double), ys As List(Of Double), gap As Double)
    If host Is Nothing OrElse host.Position Is Nothing Then Return
    If xs Is Nothing OrElse ys Is Nothing Then Return
    Dim guard As Integer = 0
    Do While guard < 8
        guard = guard + 1
        Dim moved As Boolean = False
        Dim i As Integer = 0
        Do While i < xs.Count
            Dim j As Integer = i + 1
            Do While j < xs.Count
                Dim dx As Double = xs(j) - xs(i)
                Dim dy As Double = ys(j) - ys(i)
                Dim ax As Double = Math.Abs(dx)
                Dim ay As Double = Math.Abs(dy)
                Dim near As Double = ax
                If ay > near Then near = ay
                If near < gap Then
                    ' Slide along the outline. Pushing further from the view center is what sent balloons into empty space.
                    Dim mx As Double = (xs(i) + xs(j)) / 2 - host.Position.X
                    Dim my As Double = (ys(i) + ys(j)) / 2 - host.Position.Y
                    Dim tax As Double = -my
                    Dim tay As Double = mx
                    Dim tscale As Double = Math.Abs(tax)
                    If Math.Abs(tay) > tscale Then tscale = Math.Abs(tay)
                    If tscale < 0.05 Then
                        tax = 0
                        tay = 1
                        tscale = 1
                    End If
                    Dim push As Double = (gap - near) / 2 + 0.08
                    If push < 0.2 Then push = 0.2
                    xs(i) = xs(i) - tax / tscale * push
                    ys(i) = ys(i) - tay / tscale * push
                    xs(j) = xs(j) + tax / tscale * push
                    ys(j) = ys(j) + tay / tscale * push
                    moved = True
                End If
                j = j + 1
            Loop
            i = i + 1
        Loop
        If Not moved Then Exit Do
    Loop
End Sub

Sub KeepTipsClear(sheet As Sheet, host As DrawingView, xs As List(Of Double), ys As List(Of Double))
    If xs Is Nothing OrElse ys Is Nothing Then Return
    Dim listL As Double = 0
    Dim listB As Double = 0
    Dim listR As Double = 0
    Dim listT As Double = 0
    Dim hasList As Boolean = False
    Dim titleL As Double = 0
    Dim titleB As Double = 0
    Dim titleR As Double = 0
    Dim titleT As Double = 0
    Dim hasTitle As Boolean = False
    ReadOccupied(sheet, listL, listB, listR, listT, hasList, titleL, titleB, titleR, titleT, hasTitle)
    Dim guard As Integer = 0
    Do While guard < 5
        guard = guard + 1
        Dim index As Integer = 0
        Do While index < xs.Count AndAlso index < ys.Count
            Dim x As Double = xs(index)
            Dim y As Double = ys(index)
            Try
                For Each view As DrawingView In sheet.DrawingViews
                    If view IsNot Nothing AndAlso view.Position IsNot Nothing AndAlso Not SameView(view, host) Then
                        PushTipOut(x, y, view.Position.X - view.Width / 2 - 1.6, view.Position.Y - view.Height / 2 - 1.6, view.Position.X + view.Width / 2 + 1.6, view.Position.Y + view.Height / 2 + 1.6)
                    End If
                Next
            Catch
            End Try
            If hasList Then PushTipOut(x, y, listL - 0.35, listB - 0.35, listR + 0.35, listT + 0.35)
            If hasTitle Then PushTipOut(x, y, titleL - 0.35, titleB - 0.35, titleR + 0.35, titleT + 0.35)
            xs(index) = x
            ys(index) = y
            index = index + 1
        Loop
    Loop
End Sub

Function SameView(a As DrawingView, b As DrawingView) As Boolean
    If a Is Nothing OrElse b Is Nothing Then Return False
    Try
        If a.Name <> "" AndAlso a.Name = b.Name Then Return True
    Catch
    End Try
    If a.Position Is Nothing OrElse b.Position Is Nothing Then Return False
    If Math.Abs(a.Position.X - b.Position.X) > 0.05 Then Return False
    If Math.Abs(a.Position.Y - b.Position.Y) > 0.05 Then Return False
    Return True
End Function

Sub PushTipOut(ByRef x As Double, ByRef y As Double, minX As Double, minY As Double, maxX As Double, maxY As Double)
    If x < minX OrElse x > maxX OrElse y < minY OrElse y > maxY Then Return
    Dim leftD As Double = x - minX
    Dim rightD As Double = maxX - x
    Dim lowD As Double = y - minY
    Dim highD As Double = maxY - y
    Dim best As Double = leftD
    Dim which As Integer = 1
    If rightD < best Then
        best = rightD
        which = 2
    End If
    If lowD < best Then
        best = lowD
        which = 3
    End If
    If highD < best Then which = 4
    Dim gap As Double = 0.15
    If which = 1 Then x = minX - gap
    If which = 2 Then x = maxX + gap
    If which = 3 Then y = minY - gap
    If which = 4 Then y = maxY + gap
End Sub

Sub ClampTips(sheet As Sheet, xs As List(Of Double), ys As List(Of Double))
    If xs Is Nothing OrElse ys Is Nothing Then Return
    Dim margin As Double = 1.15
    Dim index As Integer = 0
    Do While index < xs.Count AndAlso index < ys.Count
        If xs(index) < margin Then xs(index) = margin
        If ys(index) < margin Then ys(index) = margin
        If xs(index) > sheet.Width - margin Then xs(index) = sheet.Width - margin
        If ys(index) > sheet.Height - margin Then ys(index) = sheet.Height - margin
        index = index + 1
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

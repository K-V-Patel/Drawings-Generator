' ExportTemplates.vb
' External iLogic rule for Autodesk Inventor 2025.
' Reads every .idw and .dwg in the shop template folder and writes
' drawgen-templates.json on the Desktop. Drop that file on the
' Templates page in Drawings Generator.
'
' The folder is the English template directory:
' C:\Users\Public\Documents\Autodesk\Inventor 2025\Templates\en-US
' Subfolders are included. They show up as tabs in Inventor's New dialog.
' Part and assembly templates (.ipt, .iam) are listed but not opened.

Imports System.Text
Imports System.IO

Sub Main()
    Dim folder As String = "C:\Users\Public\Documents\Autodesk\Inventor 2025\Templates\en-US"
    If Not Directory.Exists(folder) Then
        MessageBox.Show("Template folder was not found:" & vbLf & folder, "Drawings Generator")
        Return
    End If

    Dim files As New System.Collections.Generic.List(Of String)
    For Each path As String In Directory.GetFiles(folder, "*.*", SearchOption.AllDirectories)
        Dim ext As String = IO.Path.GetExtension(path).ToLowerInvariant()
        If ext = ".idw" OrElse ext = ".dwg" Then files.Add(path)
    Next
    files.Sort()

    Dim items As New StringBuilder()
    Dim opened As Integer = 0
    Dim failed As Integer = 0
    Dim wasSilent As Boolean = ThisApplication.SilentOperation
    ThisApplication.SilentOperation = True
    Try
        For Each path As String In files
            If items.Length > 0 Then items.Append(",")
            items.Append(Describe(folder, path, opened, failed))
        Next
    Finally
        ThisApplication.SilentOperation = wasSilent
    End Try

    Dim json As String = "{" &
        """schema"":""drawgen-templates/1""," &
        """folder"":""" & J(folder) & """," &
        """templates"":[" & items.ToString() & "]" &
    "}"

    Dim desktop As String = Environment.GetFolderPath(Environment.SpecialFolder.Desktop)
    Dim outPath As String = IO.Path.Combine(desktop, "drawgen-templates.json")
    File.WriteAllText(outPath, json, Encoding.UTF8)
    MessageBox.Show(
        "Wrote " & outPath & vbLf &
        "Drawing templates: " & files.Count.ToString() & vbLf &
        "Opened: " & opened.ToString() & "   Could not open: " & failed.ToString(),
        "Drawings Generator")
End Sub

Function Describe(folder As String, path As String, ByRef opened As Integer, ByRef failed As Integer) As String
    Dim relative As String = path.Substring(folder.Length).TrimStart("\"c, "/"c)
    Dim fileName As String = IO.Path.GetFileName(path)
    Dim widthIn As String = ""
    Dim heightIn As String = ""
    Dim titleBlock As String = ""
    Dim borderName As String = ""
    Dim problem As String = ""

    Dim drawDoc As DrawingDocument = Nothing
    Dim alreadyOpen As Boolean = False
    Try
        For Each openDoc As Document In ThisApplication.Documents
            If String.Equals(openDoc.FullFileName, path, StringComparison.OrdinalIgnoreCase) Then
                drawDoc = TryCast(openDoc, DrawingDocument)
                alreadyOpen = True
                Exit For
            End If
        Next
        If drawDoc Is Nothing AndAlso Not alreadyOpen Then
            drawDoc = TryCast(ThisApplication.Documents.Open(path, False), DrawingDocument)
        End If
        If drawDoc Is Nothing Then
            problem = "Not a drawing document"
            failed += 1
        Else
            Dim sheet As Sheet = drawDoc.ActiveSheet
            Dim uom As UnitsOfMeasure = drawDoc.UnitsOfMeasure
            Dim wide As Double = uom.ConvertUnits(sheet.Width, UnitsTypeEnum.kDatabaseLengthUnits, UnitsTypeEnum.kInchLengthUnits)
            Dim high As Double = uom.ConvertUnits(sheet.Height, UnitsTypeEnum.kDatabaseLengthUnits, UnitsTypeEnum.kInchLengthUnits)
            widthIn = wide.ToString("0.###")
            heightIn = high.ToString("0.###")
            If sheet.TitleBlock IsNot Nothing Then titleBlock = sheet.TitleBlock.Definition.Name
            If sheet.Border IsNot Nothing Then borderName = sheet.Border.Definition.Name
            opened += 1
        End If
    Catch ex As Exception
        problem = ex.Message
        failed += 1
    Finally
        If drawDoc IsNot Nothing AndAlso Not alreadyOpen Then
            Try
                drawDoc.Close(False)
            Catch
            End Try
        End If
    End Try

    Dim sizePart As String = ""
    If widthIn <> "" AndAlso heightIn <> "" Then
        sizePart = ",""sheetWidthIn"":" & widthIn & ",""sheetHeightIn"":" & heightIn
    End If
    Dim errorPart As String = ""
    If problem <> "" Then errorPart = ",""error"":""" & J(problem) & """"
    Return "{""fileName"":""" & J(fileName) & """,""relativePath"":""" & J(relative) & """" &
        sizePart &
        ",""titleBlock"":""" & J(titleBlock) & """,""border"":""" & J(borderName) & """" &
        errorPart & "}"
End Function

Function J(value As String) As String
    If value Is Nothing Then Return ""
    Return value.Replace("\", "\\").Replace("""", "\""").Replace(vbCr, " ").Replace(vbLf, " ")
End Function

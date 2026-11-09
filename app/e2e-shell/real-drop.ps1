<#
  R15.2 (E2E_SHELL): a real OS file drop onto the app window.

  This is a genuine OLE drag and drop, done as a user drags files out of Explorer: a small source
  window of this helper gets a real left-button press (mouse_event), its MouseDown calls ole32
  DoDragDrop with a CF_HDROP IDataObject (a WinForms DataObject holding the file list) and an
  IDropSource that drops when the button is released. Real mouse moves then carry the cursor onto
  the conversation area and hover there; OLE finds the drop target under the cursor (the WebView2
  window, Chrome_RenderWidgetHostHWND, whose root is the app window), calls its IDropTarget
  DragEnter / DragOver, and on the button release IDropTarget::Drop. WebView2 turns that into
  HTML5 dragenter / dragover / drop events in the page; nothing here touches the page's JavaScript.

  Needs an unlocked interactive desktop. It takes the mouse for about 4 s, makes the app window
  topmost for that time and takes the foreground (a press on its own window).

  Usage: real-drop.ps1 -AppPid <pid> -X <css px> -Y <css px> -Dpr <devicePixelRatio> -Files a.jpg,b.jpg
         real-drop.ps1 -MakeJpgs <dir>      (writes page1..3.jpg: synthetic test pages, no student data)
  Output: one line "hr=… effect=… target=… root_ok=…"; exit 0 when the window under the drop
  point belongs to the app and OLE reports DRAGDROP_S_DROP with DROPEFFECT_COPY.
#>
param(
  [int]$AppPid,
  [double]$X,
  [double]$Y,
  [double]$Dpr = 1,
  [string[]]$Files,
  [string]$MakeJpgs,
  [int]$HoldMs = 2500
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

if ($MakeJpgs) {
  New-Item -ItemType Directory -Force $MakeJpgs | Out-Null
  $out = @()
  foreach ($i in 1..3) {
    $bmp = New-Object System.Drawing.Bitmap 600, 840
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.Clear([System.Drawing.Color]::White)
    $font = New-Object System.Drawing.Font "Arial", 28
    $g.DrawString("Synthetic test page $i", $font, [System.Drawing.Brushes]::Black, 40, 40)
    for ($l = 0; $l -lt 12; $l++) {
      $g.DrawString("$($l + 1). Choose the correct answer: A B C D", (New-Object System.Drawing.Font "Arial", 14), [System.Drawing.Brushes]::Black, 40, 140 + 50 * $l)
    }
    $g.Dispose()
    $p = Join-Path $MakeJpgs "page$i.jpg"
    $bmp.Save($p, [System.Drawing.Imaging.ImageFormat]::Jpeg)
    $bmp.Dispose()
    $out += $p
  }
  $out
  exit 0
}

$src = @"
using System;
using System.Collections.Specialized;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;
using ComIDataObject = System.Runtime.InteropServices.ComTypes.IDataObject;

[ComImport, Guid("00000121-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IOleDropSource {
  [PreserveSig] int QueryContinueDrag(int fEscapePressed, int grfKeyState);
  [PreserveSig] int GiveFeedback(int dwEffect);
}

/// The standard OLE drop source rule (as Explorer's): drop when the left button is released,
/// cancel on Esc. A safety cap cancels a drag that never ends.
public class ButtonDropSource : IOleDropSource {
  public const int S_OK = 0, DRAGDROP_S_DROP = 0x40100, DRAGDROP_S_CANCEL = 0x40101, USEDEFAULTCURSORS = 0x40102;
  readonly Stopwatch clock = Stopwatch.StartNew();
  public int Calls;
  public int QueryContinueDrag(int esc, int keys) {
    Calls++;
    if (esc != 0 || clock.ElapsedMilliseconds > 20000) return DRAGDROP_S_CANCEL;
    return (keys & 1 /* MK_LBUTTON */) == 0 ? DRAGDROP_S_DROP : S_OK;
  }
  public int GiveFeedback(int effect) { return USEDEFAULTCURSORS; }
}

public static class RealDrop {
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern int GetWindowTextLength(IntPtr h);
  [DllImport("user32.dll")] static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] static extern IntPtr WindowFromPoint(POINT p);
  [DllImport("user32.dll")] static extern IntPtr GetAncestor(IntPtr h, uint flags);
  [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] static extern void mouse_event(uint flags, int dx, int dy, uint data, UIntPtr extra);
  [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, System.Text.StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool SetProcessDpiAwarenessContext(IntPtr ctx);
  [DllImport("ole32.dll")] static extern int OleInitialize(IntPtr r);
  [DllImport("ole32.dll")] static extern int DoDragDrop(ComIDataObject data, IOleDropSource source, int okEffects, out int effect);

  public static IntPtr MainWindow(uint pid) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => {
      uint p; GetWindowThreadProcessId(h, out p);
      if (p == pid && IsWindowVisible(h) && GetWindowTextLength(h) > 0) { found = h; return false; }
      return true;
    }, IntPtr.Zero);
    return found;
  }

  static string ClassOf(IntPtr h) { var s = new System.Text.StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }

  public static string Run(uint pid, double x, double y, double dpr, string[] files, int holdMs) {
    SetProcessDpiAwarenessContext(new IntPtr(-4)); // per-monitor v2: physical pixels everywhere
    IntPtr hwnd = MainWindow(pid);
    if (hwnd == IntPtr.Zero) throw new Exception("no visible window for pid " + pid);

    // Foreground + topmost, so the drop point is really on this window.
    ShowWindow(hwnd, 9); // SW_RESTORE
    keybd_event(0x12, 0, 0, UIntPtr.Zero); keybd_event(0x12, 0, 2, UIntPtr.Zero); // ALT: lifts the foreground lock
    SetWindowPos(hwnd, new IntPtr(-1), 0, 0, 0, 0, 0x3); // HWND_TOPMOST, NOMOVE|NOSIZE
    BringWindowToTop(hwnd);
    SetForegroundWindow(hwnd);
    Thread.Sleep(400);

    POINT pt = new POINT();
    ClientToScreen(hwnd, ref pt);
    pt.X += (int)Math.Round(x * dpr);
    pt.Y += (int)Math.Round(y * dpr);
    IntPtr under = WindowFromPoint(pt);
    bool rootOk = GetAncestor(under, 2) == hwnd; // GA_ROOT
    string cls = ClassOf(under);

    int oi = OleInitialize(IntPtr.Zero);
    if (oi < 0) throw new Exception("OleInitialize failed");
    var data = new System.Windows.Forms.DataObject();
    var list = new StringCollection();
    list.AddRange(files);
    data.SetFileDropList(list);

    // A user's drag, with real mouse input. The drag starts on a small source window owned by
    // this helper (as a drag from Explorer starts on Explorer's window): the left button goes
    // down on it, its MouseDown starts the OLE drag (DoDragDrop captures the mouse; that needs this
    // thread to be in the foreground, which a press on our own window gives). The cursor then
    // moves onto the drop point and stays there for holdMs, so OLE calls the WebView2 window's
    // IDropTarget DragEnter and a stream of DragOver; then the button goes up: the drop source sees
    // MK_LBUTTON gone and OLE calls IDropTarget::Drop on the window under the cursor.
    var form = new System.Windows.Forms.Form();
    form.FormBorderStyle = System.Windows.Forms.FormBorderStyle.None;
    form.StartPosition = System.Windows.Forms.FormStartPosition.Manual;
    form.ShowInTaskbar = false;
    form.TopMost = true;
    form.BackColor = System.Drawing.Color.SteelBlue;
    form.Bounds = new System.Drawing.Rectangle(pt.X - 260, pt.Y - 50, 100, 100);
    POINT start = new POINT { X = pt.X - 210, Y = pt.Y };
    var source = new ButtonDropSource();
    int effect = 0, hr = -1;
    bool dragged = false;
    form.MouseDown += (s, e) => {
      if (dragged) return;
      dragged = true;
      hr = DoDragDrop(data, source, 1 /* DROPEFFECT_COPY */, out effect);
      form.Close();
    };
    form.Shown += (s, e) => {
      keybd_event(0x12, 0, 0, UIntPtr.Zero); keybd_event(0x12, 0, 2, UIntPtr.Zero);
      SetForegroundWindow(form.Handle);
      var mover = new Thread(() => {
        Thread.Sleep(400);
        SetCursorPos(start.X, start.Y);
        Thread.Sleep(150);
        mouse_event(0x2 /* LEFTDOWN */, 0, 0, 0, UIntPtr.Zero);
        Thread.Sleep(200);
        for (int k = 1; k <= 20; k++) { // the drag path: start → drop point
          SetCursorPos(start.X + (pt.X - start.X) * k / 20, start.Y + (pt.Y - start.Y) * k / 20);
          mouse_event(0x1 /* MOVE */, 0, 0, 0, UIntPtr.Zero);
          Thread.Sleep(30);
        }
        var clock = Stopwatch.StartNew();
        for (int i = 0; clock.ElapsedMilliseconds < holdMs; i++) { // hover over the drop point
          SetCursorPos(pt.X + (i % 3) - 1, pt.Y + (i % 2));
          mouse_event(0x1 /* MOVE */, 0, 0, 0, UIntPtr.Zero);
          Thread.Sleep(40);
        }
        SetCursorPos(pt.X, pt.Y);
        Thread.Sleep(100);
        mouse_event(0x4 /* LEFTUP */, 0, 0, 0, UIntPtr.Zero);
        Thread.Sleep(5000); // safety: if no drag ever started, end the helper
        if (!dragged) form.BeginInvoke(new Action(form.Close));
      });
      mover.IsBackground = true;
      mover.Start();
    };
    try {
      System.Windows.Forms.Application.Run(form);
    } finally {
      mouse_event(0x4 /* LEFTUP */, 0, 0, 0, UIntPtr.Zero); // never leave the button down
      SetWindowPos(hwnd, new IntPtr(-2), 0, 0, 0, 0, 0x3); // HWND_NOTOPMOST
    }
    return string.Format("hr=0x{0:X} effect={1} point={2},{3} target={4} root_ok={5} drag_started={6} qcd_calls={7}",
      hr, effect, pt.X, pt.Y, cls, rootOk, dragged, source.Calls);
  }
}
"@
$Files = @($Files | ForEach-Object { $_ -split "," } | Where-Object { $_ }) # -File passes "a,b,c" as one string
Add-Type -TypeDefinition $src -ReferencedAssemblies System.Windows.Forms, System.Drawing
$result = [RealDrop]::Run([uint32]$AppPid, $X, $Y, $Dpr, $Files, $HoldMs)
Write-Output $result
if ($result -match "hr=0x40100 effect=1 " -and $result -match "root_ok=True") { exit 0 } else { exit 2 }

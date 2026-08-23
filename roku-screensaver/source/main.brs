' Purpose: JellyFlam3 Roku Screensaver entry (Phase 3 guide 01).
' Requirements: JellyFlam3 registry written by VoD channel Settings (this package does not create credentials).
' Assumptions: Image-only — never Video / Sessions/Playing (idle-gate safe).

sub RunScreenSaver()
  screen = CreateObject("roSGScreen")
  m.port = CreateObject("roMessagePort")
  screen.setMessagePort(m.port)
  scene = screen.CreateScene("ScreenSaverScene")
  screen.show()

  while true
    msg = wait(0, m.port)
    if type(msg) = "roSGScreenEvent"
      if msg.isScreenClosed() then return
    end if
  end while
end sub

sub RunScreenSaverSettings()
  screen = CreateObject("roSGScreen")
  m.port = CreateObject("roMessagePort")
  screen.setMessagePort(m.port)
  scene = screen.CreateScene("ScreenSaverSettings")
  screen.show()

  while true
    msg = wait(0, m.port)
    if type(msg) = "roSGScreenEvent"
      if msg.isScreenClosed() then return
    end if
  end while
end sub

sub Main(args as dynamic)
  screen = CreateObject("roSGScreen")
  m.port = CreateObject("roMessagePort")
  screen.setMessagePort(m.port)
  scene = screen.CreateScene("HomeScene")
  screen.show()

  if args <> invalid
    scene.callFunc("handleDeepLink", args)
  end if

  input = CreateObject("roInput")
  input.setMessagePort(m.port)

  while true
    msg = wait(0, m.port)
    msgType = type(msg)
    if msgType = "roSGScreenEvent"
      if msg.isScreenClosed() then return
    else if msgType = "roInputEvent"
      info = msg.getInfo()
      if info <> invalid
        scene.callFunc("handleDeepLink", info)
      end if
    end if
  end while
end sub

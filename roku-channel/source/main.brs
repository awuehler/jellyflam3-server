sub Main(args as dynamic)
  screen = CreateObject("roSGScreen")
  m.port = CreateObject("roMessagePort")
  screen.SetMessagePort(m.port)
  scene = screen.CreateScene("HomeScene")
  screen.Show()
  ' Roku certification launch-performance beacon: the initial Scene is visible.
  scene.signalBeacon("AppLaunchComplete")

  ' Cold-launch deep link (ECP launch / input params in the manifest's
  ' supports_input_launch=1 contract).
  if args <> invalid
    scene.callFunc("handleDeepLink", args)
  end if

  ' Warm deep link: roInput delivers roInputEvent while the app is running.
  input = CreateObject("roInput")
  input.SetMessagePort(m.port)
  attachAppMemoryMonitor()

  while true
    msg = wait(0, m.port)
    msgType = type(msg)
    if msgType = "roSGScreenEvent"
      if msg.isScreenClosed() then return
    else if msgType = "roInputEvent"
      if msg.IsInput()
        info = msg.GetInfo()
        if info <> invalid
          scene.callFunc("handleDeepLink", info)
        end if
      end if
    else if msgType = "roAppMemoryNotificationEvent"
      handleAppMemoryEvent(msg)
    else if msgType = "roDeviceInfoEvent"
      handleDeviceMemoryEvent(msg)
    end if
  end while
end sub

sub attachAppMemoryMonitor()
  m.appMemoryMonitor = CreateObject("roAppMemoryMonitor")
  if m.appMemoryMonitor <> invalid
    m.appMemoryMonitor.SetMessagePort(m.port)
    m.memoryWarningEnabled = m.appMemoryMonitor.EnableMemoryWarningEvent(true)
    m.memoryLimitPercent = m.appMemoryMonitor.GetMemoryLimitPercent()
    m.channelAvailableMemory = m.appMemoryMonitor.GetChannelAvailableMemory()
    m.channelMemoryLimit = m.appMemoryMonitor.GetChannelMemoryLimit()
  end if

  ' Fallback path for devices without per-app memory cgroups (and for static analysis).
  m.deviceInfo = CreateObject("roDeviceInfo")
  if m.deviceInfo <> invalid
    m.deviceInfo.SetMessagePort(m.port)
    m.deviceInfo.EnableLowGeneralMemoryEvent(true)
  end if
end sub

sub handleAppMemoryEvent(msg as object)
  if msg = invalid then return
  info = msg.GetInfo()
  if info = invalid then return
  percent = info.lookup("MemoryUsagePercent")
  if percent = invalid then return
  refreshMemorySnapshot()
end sub

sub handleDeviceMemoryEvent(msg as object)
  if msg = invalid then return
  info = msg.GetInfo()
  if info = invalid then return
  level = info.lookup("generalMemoryLevel")
  if level = invalid then return
  refreshMemorySnapshot()
end sub

sub refreshMemorySnapshot()
  if m.appMemoryMonitor = invalid then return
  m.memoryLimitPercent = m.appMemoryMonitor.GetMemoryLimitPercent()
  m.channelAvailableMemory = m.appMemoryMonitor.GetChannelAvailableMemory()
  m.channelMemoryLimit = m.appMemoryMonitor.GetChannelMemoryLimit()
end sub

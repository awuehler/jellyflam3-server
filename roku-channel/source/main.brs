sub Main(args as dynamic)
  screen = CreateObject("roSGScreen")
  m.port = CreateObject("roMessagePort")
  screen.SetMessagePort(m.port)
  scene = screen.CreateScene("HomeScene")
  screen.Show()
  ' HomeScene owns the AppLaunchComplete beacon: Roku requires it at a fully rendered
  ' home screen or at deep-link playback, which is later than screen.Show().

  ' Cold launch: ECP / voice deep link parameters arrive on Main(args).
  if args <> invalid then applyDeepLink(scene, args)

  ' Warm deep link (cert 5.2): keep roInput on `m` so it is not garbage-collected.
  ' supports_input_launch=1 in the manifest opts the channel into this path.
  m.input = CreateObject("roInput")
  m.input.SetMessagePort(m.port)
  attachAppMemoryMonitor()

  while true
    msg = wait(0, m.port)
    msgType = type(msg)
    if msgType = "roSGScreenEvent"
      if msg.isScreenClosed() then return
    else if type(msg) = "roInputEvent"
      if msg.IsInput()
        info = msg.GetInfo()
        ' Strings mediatype / contentid match Roku's sample and Store static analysis 5.2.
        if info <> invalid and info.DoesExist("mediatype") and info.DoesExist("contentid")
          mediaType = info.mediatype
          contentId = info.contentid
          applyDeepLink(scene, { mediaType: mediaType, contentId: contentId })
        else if info <> invalid
          applyDeepLink(scene, info)
        end if
      end if
    else if msgType = "roAppMemoryNotificationEvent"
      handleAppMemoryEvent(msg)
    else if msgType = "roDeviceInfoEvent"
      handleDeviceMemoryEvent(msg)
    end if
  end while
end sub

sub applyDeepLink(scene as object, params as object)
  if scene = invalid or params = invalid then return
  scene.callFunc("handleDeepLink", params)
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

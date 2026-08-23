sub init()
  m.top.focusable = true
  m.bg = m.top.findNode("bg")
  m.text = m.top.findNode("text")
end sub

sub onLabelChanged()
  m.text.text = m.top.label
end sub

sub setActive(active as boolean)
  if active
    m.bg.color = "0x2A4A6AFF"
    m.text.color = "0xFFFFFFFF"
  else
    m.bg.color = "0x1A1A28FF"
    m.text.color = "0xE8E8F0FF"
  end if
end sub

function onKeyEvent(key as string, press as boolean) as boolean
  if not press then return false
  if key = "OK" or key = "play"
    m.top.rowSelected = true
    return true
  else if key = "up" or key = "down" or key = "left" or key = "right"
    m.top.navKey = key
    return true
  end if
  return false
end function

// Draws the Mac app icon: ApplyTwin's mark on a dark macOS-style plate (1024 canvas, 824 plate, Apple's grid).
// swift icon.swift <mark.png> <out.png>
import Cocoa

let a = CommandLine.arguments
let mark = NSImage(contentsOfFile: a[1])!
let size = 1024
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size, bitsPerSample: 8, samplesPerPixel: 4,
                           hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
let plate = NSRect(x: 100, y: 100, width: 824, height: 824)
let path = NSBezierPath(roundedRect: plate, xRadius: 185, yRadius: 185)
let shadow = NSShadow()
shadow.shadowColor = NSColor.black.withAlphaComponent(0.35)
shadow.shadowBlurRadius = 24
shadow.shadowOffset = NSSize(width: 0, height: -10)
NSGraphicsContext.saveGraphicsState()
shadow.set()
NSColor(red: 0.11, green: 0.11, blue: 0.12, alpha: 1).setFill()
path.fill()
NSGraphicsContext.restoreGraphicsState()
NSGradient(starting: NSColor(red: 0.17, green: 0.17, blue: 0.19, alpha: 1), ending: NSColor(red: 0.08, green: 0.08, blue: 0.09, alpha: 1))!
    .draw(in: path, angle: -90)
NSColor.white.withAlphaComponent(0.08).setStroke()
path.lineWidth = 2
path.stroke()
mark.draw(in: NSRect(x: 232, y: 232, width: 560, height: 560))
NSGraphicsContext.restoreGraphicsState()
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: a[2]))

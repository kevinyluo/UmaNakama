try:
    from PIL import ImageGrab
    import pyperclip
    import cv2
except ImportError:
    print("Libraries missing. Installing them...")
    import os
    os.system("pip install pillow")
    os.system("pip install pyperclip")
    os.system("pip install opencv-python")
 
def main():
 
    clipboard_data = ImageGrab.grabclipboard()
 
    if not clipboard_data:
        print("No image in clipboard")
        return
 
    clipboard_data.save("image.png", "PNG")
 
    image = cv2.imread("image.png")
    selection = cv2.selectROI("image", image)
 
    x, y, width, height = selection
    pyperclip.copy(f"({x}, {y}, {width}, {height})")
 
 
if __name__ == "__main__":
    main()

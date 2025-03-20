def handle_panic(self, *args, **kwargs):
    """Handle panic action (hide windows quickly)"""
    # Check if panic is disabled
    if hasattr(self, 'is_panic_disabled') and self.is_panic_disabled:
        logger.info("Panic action blocked - currently disabled during key remapping")
        return False
        
    logger.info("Handling panic action")
    self.withdraw()
    
    # Also hide any top level windows
    for window in self.winfo_children():
        if isinstance(window, tk.Toplevel):
            window.withdraw()
            
    return True 
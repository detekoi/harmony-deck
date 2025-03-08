#!/usr/bin/env python3
import rumps
import subprocess
import sys
import os
import threading
import time
import json

class JamDeckApp(rumps.App):
    def __init__(self):
        # Path to menu bar icon (template means it adapts to light/dark mode)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jamdeck-template.png")
        
        super(JamDeckApp, self).__init__("Jam Deck", icon=icon_path, template=True)
        
        # Set up menu items
        self.server_running = False
        self.server_process = None
        self.server_thread = None
        
        # Load saved scenes
        self.scenes = self.load_scenes()
        
        # Load user preferences
        self.preferences = self.load_preferences()
        
        # Configure all menu items at once
        server_item = rumps.MenuItem("Start Server", callback=self.toggle_server)
        copy_scenes_menu = self.create_copy_scenes_menu()
        
        # Create checkable "Auto-open URLs in Browser" menu item
        auto_open_item = rumps.MenuItem("Auto-open URLs in Browser", callback=self.toggle_auto_open)
        # Set initial state based on preferences
        auto_open_item.state = self.preferences.get("auto_open_urls", True)
        
        self.menu = [
            server_item,
            None,  # Separator
            copy_scenes_menu,
            None,  # Separator
            rumps.MenuItem("Open in Browser", callback=self.open_browser),
            auto_open_item,
            None,  # Separator
            rumps.MenuItem("About", callback=self.show_about)
        ]
        
        # Update menu text based on current state
        self.update_menu_state()

    def update_menu_state(self):
        """Update the menu items based on server state"""
        # Save current checked state of auto-open setting
        current_auto_open_state = self.menu["Auto-open URLs in Browser"].state
        
        if self.server_running:
            self.menu["Start Server"].title = "Stop Server"
            # Enable "Open in Browser" when server is running
            self.menu["Open in Browser"].set_callback(self.open_browser)
        else:
            self.menu["Start Server"].title = "Start Server"
            # Disable "Open in Browser" when server is not running
            self.menu["Open in Browser"].set_callback(self.server_not_running)
            
        # Preserve the checked state
        self.menu["Auto-open URLs in Browser"].state = current_auto_open_state

    def toggle_server(self, sender):
        """Toggle server on/off"""
        if self.server_running:
            self.stop_server()
        else:
            self.start_server()

    def start_server(self):
        """Start the music server"""
        if not self.server_running:
            try:
                # Get the directory of the current script
                script_dir = os.path.dirname(os.path.abspath(__file__))
                server_path = os.path.join(script_dir, "music_server.py")
                
                # Use Python from the current executable
                python_path = sys.executable
                
                # Start the server in a separate process
                self.server_process = subprocess.Popen(
                    [python_path, server_path],
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8'
                )
                
                # Monitor the server output in a separate thread
                self.server_thread = threading.Thread(target=self.monitor_server)
                self.server_thread.daemon = True
                self.server_thread.start()
                
                # Give server a moment to start
                time.sleep(1)
                
                # Update state
                self.server_running = True
                self.update_menu_state()
                
                # Notify user
                rumps.notification(
                    title="Jam Deck",
                    subtitle="Server Started", 
                    message="Now playing overlay is active!"
                )
            except Exception as e:
                rumps.notification(
                    title="Jam Deck",
                    subtitle="Error Starting Server", 
                    message=str(e)
                )

    def stop_server(self):
        """Stop the music server"""
        if self.server_running and self.server_process:
            try:
                # Terminate the server process
                self.server_process.terminate()
                self.server_process = None
                self.server_running = False
                self.update_menu_state()
                
                # Notify user
                rumps.notification(
                    title="Jam Deck",
                    subtitle="Server Stopped", 
                    message="Overlay is no longer available."
                )
            except Exception as e:
                rumps.notification(
                    title="Jam Deck",
                    subtitle="Error Stopping Server", 
                    message=str(e)
                )

    def monitor_server(self):
        """Monitor server output and handle process exit"""
        while self.server_process:
            # Read output line by line
            output = self.server_process.stdout.readline()
            if output:
                print(f"Server: {output.strip()}")
            
            # Check if process has exited
            if self.server_process.poll() is not None:
                # Process has terminated
                if self.server_running:
                    # If we thought it was running, it crashed
                    self.server_running = False
                    
                    # Update UI on main thread
                    rumps.App.notification(
                        title="Jam Deck",
                        subtitle="Server Stopped Unexpectedly", 
                        message="Check log for details."
                    )
                    
                    # Update menu state on main thread
                    def update():
                        self.update_menu_state()
                    rumps.Timer(0, update).start()
                break

    def open_browser(self, _):
        """Open overlay in default browser"""
        try:
            subprocess.run(["open", "http://localhost:8080"])
        except Exception as e:
            rumps.notification(
                title="Jam Deck",
                subtitle="Error", 
                message=f"Could not open browser: {str(e)}"
            )

    def server_not_running(self, _):
        """Display message when server is not running"""
        rumps.notification(
            title="Jam Deck",
            subtitle="Server Not Running", 
            message="Start the server first."
        )
        
    def toggle_auto_open(self, sender):
        """Toggle the auto-open browser setting"""
        # Toggle the checkbox state
        sender.state = not sender.state
        
        # Update preferences
        self.preferences["auto_open_urls"] = sender.state
        self.save_preferences()

    def show_about(self, _):
        """Show about dialog"""
        rumps.alert(
            title="About Jam Deck",
            message=(
                "Jam Deck for OBS\n"
                "Version 1.0.0\n\n"
                "Display your Apple Music tracks in OBS.\n\n"
                "OBS Tip - Width: Recommended minimum 400px, Height: 140px\n\n"
                "© 2025 Henry Manes"
            )
        )
    
    def load_scenes(self):
        """Load saved scenes from config file"""
        try:
            config_path = os.path.join(os.path.expanduser("~"), ".jamdeck_scenes")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    scenes = [line.strip() for line in f.readlines() if line.strip()]
                    if not scenes:
                        return ["default"]
                    return scenes
            return ["default"]
        except Exception:
            return ["default"]

    def save_scenes(self):
        """Save scenes to config file"""
        try:
            config_path = os.path.join(os.path.expanduser("~"), ".jamdeck_scenes")
            with open(config_path, "w") as f:
                for scene in self.scenes:
                    f.write(f"{scene}\n")
        except Exception as e:
            rumps.notification("Jam Deck", "Error", f"Could not save scenes: {str(e)}")
            
    def load_preferences(self):
        """Load user preferences from config file"""
        try:
            prefs_path = os.path.join(os.path.expanduser("~"), ".jamdeck_prefs")
            if os.path.exists(prefs_path):
                with open(prefs_path, "r") as f:
                    return json.load(f)
            return {"auto_open_urls": True}  # Default: auto-open is enabled
        except Exception:
            return {"auto_open_urls": True}  # Default on error
            
    def save_preferences(self):
        """Save user preferences to config file"""
        try:
            prefs_path = os.path.join(os.path.expanduser("~"), ".jamdeck_prefs")
            with open(prefs_path, "w") as f:
                json.dump(self.preferences, f)
        except Exception as e:
            rumps.notification("Jam Deck", "Error", f"Could not save preferences: {str(e)}")

    def create_copy_scenes_menu(self):
        """Create the copy scenes submenu"""
        # Create copy scenes submenu
        copy_scenes_menu = rumps.MenuItem("Copy Scene URL")
        
        # Add each scene as a menu item
        for scene in self.scenes:
            item = rumps.MenuItem(scene, callback=self.copy_scene_url)
            copy_scenes_menu.add(item)
        
        # Add separator and management options
        copy_scenes_menu.add(None)  # Separator
        copy_scenes_menu.add(rumps.MenuItem("Add New Scene...", callback=self.add_new_scene))
        
        # Create and add the manage scenes submenu
        manage_scenes_menu = self.build_manage_scenes_menu()
        copy_scenes_menu.add(manage_scenes_menu)
        
        return copy_scenes_menu
        
    def rebuild_copy_scenes_menu(self):
        """Rebuild the copy scenes menu after changes"""
        if "Copy Scene URL" in self.menu:
            # Create new copy scenes menu with updated nested menus
            new_copy_scenes_menu = self.create_copy_scenes_menu()
            
            # Replace existing menu
            index = self.menu._menu.indexOfItemWithTitle_("Copy Scene URL")
            if index != -1:
                self.menu._menu.removeItemAtIndex_(index)
                self.menu._menu.insertItem_atIndex_(new_copy_scenes_menu._menuitem, index)
    
    def copy_scene_url(self, sender):
        """Copy the URL for the selected scene to clipboard and optionally open in browser"""
        try:
            # Base URL
            base_url = "http://localhost:8080"
            
            # Add scene parameter if not default
            scene_name = sender.title
            if scene_name and scene_name != "default":
                url = f"{base_url}/?scene={scene_name}"
            else:
                url = base_url
            
            # Copy URL to clipboard using pbcopy
            subprocess.run("pbcopy", text=True, input=url)
            
            # Check if auto-open is enabled and server is running
            should_open_browser = (
                self.preferences.get("auto_open_urls", True) and 
                self.server_running
            )
            
            # Open browser if enabled
            if should_open_browser:
                subprocess.run(["open", url])
                
                # Notification message differs when browser is opened
                rumps.notification(
                    title="Jam Deck",
                    subtitle="URL Copied & Opened",
                    message=f"Scene '{scene_name}' URL copied and opened in browser"
                )
            else:
                rumps.notification(
                    title="Jam Deck",
                    subtitle="URL Copied",
                    message=f"OBS source URL for scene '{scene_name}' copied to clipboard"
                )
        except Exception as e:
            rumps.notification(
                title="Jam Deck",
                subtitle="Error",
                message=f"Could not copy URL: {str(e)}"
            )

    def add_new_scene(self, _):
        """Show dialog to add a new scene"""
        response = rumps.Window(
            title="Add New Scene",
            message="Enter a name for the new scene:",
            dimensions=(300, 20)
        ).run()
        
        if response.clicked and response.text:
            # Sanitize name for URL (replace spaces with hyphens, remove special chars)
            scene_name = "".join(c if c.isalnum() else "-" for c in response.text)
            
            # Check if name exists
            if scene_name in self.scenes:
                rumps.alert("Scene Error", f"Scene '{scene_name}' already exists.")
                return
            
            # Add the new scene
            self.scenes.append(scene_name)
            self.save_scenes()
            
            # Rebuild copy scenes menu
            self.rebuild_copy_scenes_menu()

    def manage_scenes(self, _):
        """Show the Manage Scenes menu (this is a menu item callback but not used directly)"""
        # This function is just a placeholder for menu item callback
        # The actual menu is built in build_manage_scenes_menu and attached in create_copy_scenes_menu
        pass
        
    def build_manage_scenes_menu(self):
        """Generate the dynamic submenu for scene management"""
        manage_scenes_menu = rumps.MenuItem("Manage Scenes")
        
        # Add each scene as a menu item with its own submenu
        for scene in self.scenes:
            scene_item = rumps.MenuItem(f"Scene: {scene}")
            
            # Only add operation submenus for non-default scenes
            if scene != "default":
                # Create callbacks with scene name embedded in the callback
                rename_callback = lambda sender, scene_name=scene: self.rename_scene_with_name(sender, scene_name)
                delete_callback = lambda sender, scene_name=scene: self.delete_scene_with_name(sender, scene_name)
                
                rename_item = rumps.MenuItem("Rename...", callback=rename_callback)
                delete_item = rumps.MenuItem("Delete", callback=delete_callback)
                scene_item.add(rename_item)
                scene_item.add(delete_item)
            else:
                # Make default scene item appear disabled
                scene_item.set_callback(None)
            
            manage_scenes_menu.add(scene_item)
        
        return manage_scenes_menu
        
    def rename_scene_with_name(self, sender, scene_name):
        """Rename a scene using the passed scene name"""
        print(f"Renaming scene: {scene_name}")
        
        # Show rename dialog
        new_name = rumps.Window(
            title="Rename Scene",
            message=f"Enter new name for '{scene_name}':",
            dimensions=(300, 20)
        ).run()
        
        if new_name.clicked and new_name.text:
            # Sanitize name
            sanitized_name = "".join(c if c.isalnum() else "-" for c in new_name.text)
            
            # Find and update scene name
            if scene_name in self.scenes:
                index = self.scenes.index(scene_name)
                self.scenes[index] = sanitized_name
                self.save_scenes()
                
                # Rebuild menus
                self.rebuild_copy_scenes_menu()
    
    def delete_scene_with_name(self, sender, scene_name):
        """Delete a scene using the passed scene name"""
        print(f"Deleting scene: {scene_name}")
        
        # Confirm deletion
        confirm = rumps.alert(
            title="Confirm Deletion",
            message=f"Are you sure you want to delete the scene '{scene_name}'?",
            ok="No, Keep It",
            cancel="Yes, Delete It"
        )
        
        if confirm != 1:  # Not OK button (so "Yes, Delete It")
            # Remove the scene
            if scene_name in self.scenes:
                self.scenes.remove(scene_name)
                self.save_scenes()
                
                # Rebuild menus
                self.rebuild_copy_scenes_menu()
    

if __name__ == "__main__":
    app = JamDeckApp()
    # Auto-start server when app launches
    app.start_server()
    app.run()
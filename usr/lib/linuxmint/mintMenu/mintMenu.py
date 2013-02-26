#!/usr/bin/env python
import gi
gi.require_version("Gtk", "2.0")

try:
    import os
    import sys
    import commands
    import gettext
    import matevfs
    import traceback
    import time
    import gc
    import xdg.Config
    from gi.repository import Gtk
    from gi.repository import Pango
    from gi.repository import MatePanelApplet
except Exception, e:
    print e
    sys.exit( 1 )

from easybuttons import iconManager
from easygconf import EasyGConf
from execute import *

global mbindkey
# Load the key binding lib (developped by deskbar-applet, copied into mintMenu so we don't end up with an unnecessary dependency)
try:
    from deskbar.core.keybinder import tomboy_keybinder_bind as bind_key
except Exception, cause:
    print "*********** Keybind Driver Load Failure **************"
    print "Error Report : ", str(cause)
    pass

# Rename the process
architecture = commands.getoutput("uname -a")
if (architecture.find("x86_64") >= 0):
    import ctypes
    libc = ctypes.CDLL('libc.so.6')
    libc.prctl(15, 'mintmenu', 0, 0, 0)
else:
    import dl
    if os.path.exists('/lib/libc.so.6'):
        libc = dl.open('/lib/libc.so.6')
        libc.call('prctl', 15, 'mintmenu', 0, 0, 0)
    elif os.path.exists('/lib/i386-linux-gnu/libc.so.6'):
        libc = dl.open('/lib/i386-linux-gnu/libc.so.6')
        libc.call('prctl', 15, 'mintmenu', 0, 0, 0)

# i18n
gettext.install("mintmenu", "/usr/share/linuxmint/locale")

NAME = _("Menu")
PATH = os.path.abspath( os.path.dirname( sys.argv[0] ) )

ICON = "/usr/lib/linuxmint/mintMenu/visualisation-logo.png"
MINT_MENU_GLADE = "/usr/lib/linuxmint/mintMenu/mintMenu.glade"

sys.path.append( os.path.join( PATH , "plugins") )

windowManager = os.getenv("DESKTOP_SESSION")
if not windowManager:
    windowManager = "MATE"
xdg.Config.setWindowManager( windowManager.upper() )


class Handler(object):
    def __init__(self):
        #self.builder = builder
        #self.window_id = window_id
        #self.package = package

    def on_cancel_button_clicked(self, *args):
        Gtk.main_quit()


class MainWindow( object ):
    """This is the main class for the application"""

    def __init__( self, toggleButton ):

        self.path = PATH
        sys.path.append( os.path.join( self.path, "plugins") )

        self.detect_desktop_environment()

        self.icon = ICON

        self.toggle = toggleButton
        # Load glade file and extract widgets
        self.builder = Gtk.Builder()
        self.builder.add_from_file(MINT_REMOVE_GLADE)
        self.window     = self.builder.get_object( "mainWindow" )
        self.paneholder = self.builder.get_object( "paneholder" )
        self.border     = self.builder.get_object( "border" )

        self.panesToColor = [ ]
        self.headingsToColor = [ ]

        self.window.connect( "map-event", self.onMap )
        self.window.connect( "show", self.onShow )
        self.window.connect( "unmap-event", self.onUnmap )
        self.window.connect( "button-press-event", self.onButtonPress )
        self.window.connect( "key-press-event", self.onKeyPress )
        self.window.connect( "grab-broken-event", self.onGrabBroken )
        self.window.connect("destroy", Gtk.main_quit)

        self.window.stick()

        plugindir = os.path.join( os.path.expanduser( "~" ), ".linuxmint/mintMenu/plugins" )
        sys.path.append( plugindir )

        dic = {"on_window1_destroy" : self.quit_cb}
        wTree.signal_autoconnect( dic )

        self.builder.connect_signals(Handler())

        self.gconf = EasyGConf( "/apps/mintMenu/" )

        self.get_gconf_entries()
        self.setup_mint_menu_border()
        self.setup_mint_menu_opacity()
        self.setup_tooltips()

        self.populate_plugins()

        self.setup_gconf_notify()

    def setup_tooltips(self):
        self.tooltips = Gtk.Tooltips()
        if self.globalEnableTooltips and self.enableTooltips:
            self.tooltips.enable()
        else:
            self.tooltips.disable()

    def wakePlugins( self ):
        # Call each plugin and let them know we're showing up
        for plugin in self.plugins.values():
            if hasattr( plugin, "destroy" ):
                plugin.wake()

    def toggleTooltipsEnabled( self, client, connection_id, entry, args ):
        if entry.get_key() == "/apps/panel/global/tooltips_enabled":
            self.globalEnableTooltips = entry.get_value().get_bool()
        else:
            self.enableTooltips = entry.get_value().get_bool()

        if self.globalEnableTooltips and self.enableTooltips:
            self.tooltips.enable()
        else:
            self.tooltips.disable()

    def toggleStartWithFavorites( self, client, connection_id, entry, args ):
        self.startWithFavorites = entry.get_value().get_bool()    

    def toggleBorderWidth( self, client, connection_id, entry, args ):
        self.borderwidth = entry.get_value().get_int()
        self.setup_mint_menu_border()

    def toggleOpacity( self, client, connection_id, entry, args ):
        self.opacity = entry.get_value().get_int()
        self.setup_mint_menu_opacity()

    def toggleUseCustomColor( self, client, connection_id, entry, args ):
        self.usecustomcolor = entry.get_value().get_bool()
        self.setup_mint_menu_border()
        self.set_pane_colors( self.panesToColor )
        self.set_heading_style( self.headingsToColor )

    def toggleCustomBorderColor( self, client, connection_id, entry, args ):
        self.custombordercolor = entry.get_value().get_string()
        self.setup_mint_menu_border()

    def toggleCustomBackgroundColor( self, client, connection_id, entry, args ):
        self.customcolor = entry.get_value().get_string()
        self.set_pane_colors( self.panesToColor )

    def toggleCustomHeadingColor( self, client, connection_id, entry, args ):
        self.customheadingcolor = entry.get_value().get_string()
        self.set_heading_style( self.headingsToColor )

    def get_gconf_entries(self):
        self.pluginlist          = self.gconf.get( "list-string", "plugins_list",['places', 'system_management', 'newpane', 'applications'] )
        self.dottedfile          = os.path.join( self.path, "dotted.png")

        self.usecustomcolor      = self.gconf.get( "bool", "use_custom_color", False )
        self.customcolor         = self.gconf.get( "color", "custom_color", "#EEEEEE" )
        self.customheadingcolor  = self.gconf.get( "color", "custom_heading_color", "#001155" )
        self.custombordercolor   = self.gconf.get( "color", "custom_border_color", "#001155" )

        self.borderwidth          = self.gconf.get( "int", "border_width", 1 )
        self.opacity              = self.gconf.get( "int", "opacity", 98 )
        self.offset               = self.gconf.get( "int", "mintMenu_offset", 0 )        
        self.enableTooltips       = self.gconf.get( "bool", "tooltips_enabled", True )
        self.globalEnableTooltips = self.gconf.get( "bool", "/apps/panel/global/tooltips_enabled", True )        
        self.startWithFavorites   = self.gconf.get( "bool", "start_with_favorites", False )

    def setup_mint_menu_border( self ):
        if self.usecustomcolor:
            self.window.modify_bg( Gtk.StateType.NORMAL, Gdk.color_parse( self.custombordercolor ) )
        else:
            self.window.modify_bg( Gtk.StateType.NORMAL, self.window.rc_get_style().bg[ Gtk.StateType.SELECTED ] )
        self.border.set_padding( self.borderwidth, self.borderwidth, self.borderwidth, self.borderwidth )        

    def setup_mint_menu_opacity( self ):
        print "Opacity is: " + str(self.opacity)
        opacity = float(self.opacity) / float(100)
        print "Setting opacity to: " + str(opacity)
        self.window.set_opacity(opacity)
        
    def detect_desktop_environment (self):
        self.de = "mate"
        try:
            de = os.environ["DESKTOP_SESSION"]
            if de in ["gnome", "gnome-shell", "mate", "kde", "xfce"]:
                self.de = de
            else:
                if os.path.exists("/usr/bin/caja"):
                    self.de = "mate"
                elif os.path.exists("/usr/bin/thunar"):
                    self.de = "xfce"
        except Exception, detail:
            print detail

    def setup_gconf_notify(self):
        self.gconf.notifyAdd( "plugins_list", self.RegenPlugins )

        self.gconf.notifyAdd( "start_with_favorites", self.toggleStartWithFavorites )
        self.gconf.notifyAdd( "/apps/panel/global/tooltips_enabled", self.toggleTooltipsEnabled )
        self.gconf.notifyAdd( "tooltips_enabled", self.toggleTooltipsEnabled )

        self.gconf.notifyAdd( "use_custom_color", self.toggleUseCustomColor )
        self.gconf.notifyAdd( "custom_border_color", self.toggleCustomBorderColor )
        self.gconf.notifyAdd( "custom_heading_color", self.toggleCustomHeadingColor )
        self.gconf.notifyAdd( "custom_color", self.toggleCustomBackgroundColor )
        self.gconf.notifyAdd( "border_width", self.toggleBorderWidth )
        self.gconf.notifyAdd( "opacity", self.toggleOpacity )

    def populate_plugins( self ):
        self.panesToColor = [ ]
        self.headingsToColor = [ ]
        start = time.time()
        PluginPane = Gtk.EventBox()
        PluginPane.show()
        PaneLadder = Gtk.VBox( False, 0 )
        PluginPane.add( PaneLadder )
        self.set_pane_colors( [ PluginPane ] )
        ImageBox = Gtk.EventBox()
        self.set_pane_colors( [ ImageBox ] )
        ImageBox.show()

        seperatorImage = GdkPixbuf.Pixbuf.new_from_file( self.dottedfile )

        self.plugins = {}

        for plugin in self.pluginlist:
            if plugin in self.plugins:
                print u"Duplicate plugin in list: ", plugin
                continue

            if plugin != "newpane":
                try:
                    X = __import__( plugin )
                    # If no parameter passed to plugin it is autonomous
                    if X.pluginclass.__init__.func_code.co_argcount == 1:
                        MyPlugin = X.pluginclass()
                    else:
                        # pass mintMenu and togglebutton instance so that the plugin can use it
                        MyPlugin = X.pluginclass( self, self.toggle, self.de )

                    if not MyPlugin.icon:
                        MyPlugin.icon = "mate-logo-icon.png"

                    #if hasattr( MyPlugin, "hideseparator" ) and not MyPlugin.hideseparator:
                    #    Image1 = Gtk.Image()
                    #    Image1.set_from_pixbuf( seperatorImage )
                    #    if not ImageBox.get_child():
                    #        ImageBox.add( Image1 )
                    #        Image1.show()

                    #print u"Loading plugin '" + plugin + "' : sucessful"
                except Exception, e:
                    MyPlugin = Gtk.EventBox() #Fake class for MyPlugin
                    MyPlugin.heading = _("Couldn't load plugin:") + " " + plugin
                    MyPlugin.content_holder = Gtk.EventBox()

                    # create traceback
                    info = sys.exc_info()

                    errorLabel = Gtk.Label( "\n".join(traceback.format_exception( info[0], info[1], info[2] )).replace("\\n", "\n") )
                    errorLabel.set_selectable( True )
                    errorLabel.set_line_wrap( True )
                    errorLabel.set_alignment( 0.0, 0.0 )
                    errorLabel.set_padding( 5, 5 )
                    errorLabel.show()

                    MyPlugin.content_holder.add( errorLabel )
                    MyPlugin.add( MyPlugin.content_holder )
                    MyPlugin.width = 270
                    MyPlugin.icon = 'mate-logo-icon.png'
                    print u"Unable to load " + plugin + " plugin :-("


                self.set_pane_colors( [MyPlugin.content_holder] )


                MyPlugin.content_holder.show()

                VBox1 = Gtk.VBox( False, 0 )
                if MyPlugin.heading != "":                    
                    Label1 = Gtk.Label(label= MyPlugin.heading )
                    Align1 = Gtk.Alignment.new( 0, 0, 0, 0 )
                    Align1.set_padding( 10, 5, 10, 0 )
                    Align1.add( Label1 )
                    self.set_heading_style( [Label1] )
                    Align1.show()
                    Label1.show()

                    if not hasattr( MyPlugin, 'sticky' ) or MyPlugin.sticky == True:
                        heading = Gtk.EventBox()
                        Align1.set_padding( 0, 0, 10, 0 )
                        self.set_pane_colors( [heading] )
                        heading.set_size_request( MyPlugin.width, 30 )
                    else:
                        heading = Gtk.HBox()
                        #heading.set_relief( Gtk.ReliefStyle.NONE )
                        heading.set_size_request( MyPlugin.width, -1 )
                        #heading.set_sensitive(False)
                        #heading.connect( "button_press_event", self.TogglePluginView, VBox1, MyPlugin.icon, MyPlugin.heading, MyPlugin )

                    heading.add( Align1 )
                    heading.show()
                    VBox1.pack_start( heading, False )                    
                VBox1.show()
                MyPlugin.container = VBox1
                #Add plugin to Plugin Box under heading button
                MyPlugin.content_holder.reparent( VBox1 )

                #Add plugin to main window
                PaneLadder.pack_start( VBox1 , True, True, 0)
                PaneLadder.show()

                if MyPlugin.window:
                    MyPlugin.window.destroy()

                try:
                    if hasattr( MyPlugin, 'do_plugin' ):
                        MyPlugin.do_plugin()
                    if hasattr( MyPlugin, 'height' ):
                        MyPlugin.content_holder.set_size_request( -1, MyPlugin.height )
                    if hasattr( MyPlugin, 'itemstocolor' ):
                        self.set_pane_colors( MyPlugin.itemstocolor )                   
                except:
                    # create traceback
                    info = sys.exc_info()

                    error = _("Couldn't initialize plugin") + " " + plugin + " : " + "\n".join(traceback.format_exception( info[0], info[1], info[2] )).replace("\\n", "\n")
                    msgDlg = Gtk.MessageDialog( None, Gtk.DialogFlags.MODAL, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, error )
                    msgDlg.run();
                    msgDlg.destroy();

                self.plugins[plugin] = MyPlugin

            else:
                self.paneholder.pack_start( ImageBox, False, False, 0 )
                self.paneholder.pack_start( PluginPane, False, False, 0 )
                PluginPane = Gtk.EventBox()
                PaneLadder = Gtk.VBox( False, 0 )
                PluginPane.add( PaneLadder )
                self.set_pane_colors( [PluginPane] )
                ImageBox = Gtk.EventBox()
                self.set_pane_colors( [ImageBox] )
                ImageBox.show()
                PluginPane.show_all()

                if self.plugins and hasattr( MyPlugin, 'hideseparator' ) and not MyPlugin.hideseparator:
                    Image1 = Gtk.Image()
                    Image1.set_from_pixbuf( seperatorImage )
                    Image1.show()
                    #ImageBox.add( Image1 )
                    
                    Align1 = Gtk.Alignment.new()
                    Align1.set_padding( 0, 0, 6, 6 )
                    Align1.add(Image1)
                    ImageBox.add(Align1)
                    ImageBox.show_all()


        self.paneholder.pack_start( ImageBox, False, False, 0 )
        self.paneholder.pack_start( PluginPane, False, False, 0 )
        self.tooltips.disable()

        #print u"Loading", (time.time() - start), "s"

    def set_pane_colors( self, items ):
        for item in items:
            if item not in self.panesToColor:
                self.panesToColor.append( item )

        if self.usecustomcolor:
            for item in items:
                item.modify_bg( Gtk.StateType.NORMAL, Gdk.color_parse( self.customcolor ) )
        else:
            for item in items:
                item.modify_bg( Gtk.StateType.NORMAL, self.paneholder.rc_get_style().bg[ Gtk.StateType.NORMAL ] )

    def set_heading_style( self, items ):
        for item in items:
            if item not in self.headingsToColor:
                self.headingsToColor.append( item )

        HeadingStyle = Pango.AttrList()
        attr = Pango.AttrSize( 12000, 0, -1 )
        HeadingStyle.insert( attr )

        if self.usecustomcolor:
            headingcolor = Gdk.color_parse( self.customheadingcolor )
            attr = Pango.AttrForeground( headingcolor.red, headingcolor.green, headingcolor.blue, 0, -1 )
            HeadingStyle.insert( attr )
        #else:
            #headingcolor = self.window.rc_get_style().bg[ Gtk.StateType.SELECTED ]

        attr = Pango.AttrWeight( Pango.Weight.BOLD, 0, -1 )
        HeadingStyle.insert( attr )

        for item in items:
            item.set_attributes( HeadingStyle )

    def setTooltip( self, widget, tip, tipPrivate = None ):
        self.tooltips.set_tip( widget, tip, tipPrivate )

    def RegenPlugins( self, *args, **kargs ):
        #print
        #print u"Reloading Plugins..."
        for item in self.paneholder:
            item.destroy()

        for plugin in self.plugins.values():
            if hasattr( plugin, "destroy" ):
                plugin.destroy()

        try:
            del plugin
        except:
            pass
    
        try:
            del self.plugins
        except:
            pass

        gc.collect()

        self.get_gconf_entries()
        self.populate_plugins()

        #print NAME+u" reloaded"


    def show( self ):
        self.window.present()

        if ( "applications" in self.plugins ) and ( hasattr( self.plugins["applications"], "focusSearchEntry" ) ):
            if (self.startWithFavorites):
                self.plugins["applications"].changeTab(0)
            self.plugins["applications"].focusSearchEntry()

    def grab( self ):
        Gdk.pointer_grab( self.window.window, True, Gdk.EventMask.BUTTON_PRESS_MASK )
        Gdk.keyboard_grab( self.window.window, False )
        self.window.grab_add()

    def ungrab( self ):
        self.window.grab_remove()
        self.window.hide()
        Gdk.pointer_ungrab()
        Gdk.keyboard_ungrab()

    def onMap( self, widget, event ):
        self.grab()

    def onShow( self, widget ):
        for plugin in self.plugins.values():
            if hasattr( plugin, "onShowMenu" ):
                plugin.onShowMenu()

    def onUnmap( self, widget, event ):
        self.ungrab()

        for plugin in self.plugins.values():
            if hasattr( plugin, "onHideMenu" ):
                plugin.onHideMenu()

    def onKeyPress( self, widget, event ):
        if event.keyval == Gdk.KEY_Escape or event.keyval == Gdk.KEY_Super_L:
            self.hide()
        return False

    def onButtonPress( self, widget, event ):
        # Check if the pointer is within the menu, else hide the menu
        winatptr = Gdk.window_at_pointer()

        if winatptr:
            win = winatptr[0]
            while win:
                if win == self.window.window:
                    break
                win = win.get_parent()
            if not win:
                self.hide( True )
        else:
            self.hide( True )

        return True

    def onGrabBroken( self, widget, event ):
        if event.grab_window:
            try:
                theft = event.grab_window.get_user_data()
                theft.connect( "event", self.onGrabTheftEvent )
            except:
                self.window.hide( True )

    def onGrabTheftEvent( self, widget, event ):
        if event.type == Gdk.UNMAP or event.type == Gdk.SELECTION_CLEAR:
            self.grab()

    def hide(self, forceHide = False):        
        self.window.hide()


class MenuWin( object ):
    def __init__( self, applet, iid ):
        self.applet = applet

        self.gconf = EasyGConf( "/apps/mintMenu/" )
        self.gconf.notifyAdd( "applet_text", self.gconfEntriesChanged )
        self.gconf.notifyAdd( "theme_name", self.changeTheme )
        self.gconf.notifyAdd( "hot_key", self.gconfEntriesChanged )
        self.gconf.notifyAdd( "applet_icon", self.gconfEntriesChanged )
        self.gconf.notifyAdd( "hide_applet_icon", self.gconfEntriesChanged )
        self.gconf.notifyAdd( "applet_icon_size", self.gconfEntriesChanged )
        self.getGconfEntries()

        self.gconftheme = EasyGConf( "/desktop/mate/interface/" )
        self.gconftheme.notifyAdd( "gtk_theme", self.changeTheme )

        self.createPanelButton()

        self.applet.set_applet_flags( mateapplet.EXPAND_MINOR )
        self.applet.connect( "button-press-event", self.showMenu )
        self.applet.connect( "change-orient", self.changeOrientation )
        self.applet.connect( "change-background", self.changeBackground )
        self.applet.connect("enter-notify-event", self.enter_notify)
        self.applet.connect("leave-notify-event", self.leave_notify)
        self.mainwin = MainWindow( self.button_box )
        self.mainwin.window.connect( "map-event", lambda *args: self.applet.set_state( Gtk.StateType.SELECTED ) )
        self.mainwin.window.connect( "unmap-event", lambda *args: self.applet.set_state( Gtk.StateType.NORMAL ) )
        self.mainwin.window.connect( "size-allocate", lambda *args: self.positionMenu() )

        self.mainwin.window.set_name("mintmenu") # Name used in Gtk RC files

        icon = iconManager.getIcon( self.mainwin.icon, 1 )
        if icon:
            Gtk.window_set_default_icon( icon )

        self.propxml = """
                <popup name="button3">
                                <menuitem name="Item 1" verb="Preferences" label="%s" pixtype="stock" pixname="gtk-preferences" />
                                <menuitem name="Item 1" verb="Edit" label="%s" pixtype="stock" pixname="gtk-edit" />
                                <menuitem name="Item 2" verb="Reload" label="%s" pixtype="stock" pixname="gtk-refresh" />
                                <menuitem name="Item 3" verb="About" label="%s" pixtype="stock" pixname="gtk-about" />
                </popup>
                """ % ( _("Preferences"), _("Edit menu"), _("Reload plugins"), _("About") )
        self.verbs = [ ("Preferences", self.showPreferences), ("Edit", self.showMenuEditor), ("About", self.showAboutDialog), ("Reload",self.mainwin.RegenPlugins) ]
        self.bind_hot_key()

    def onBindingPress(self):
        try:
            if self.mainwin.window.flags() & Gtk.VISIBLE:
                self.mainwin.window.hide()
                self.mainwin.toggle.set_active(False)
            else:
                MenuWin.showMenu(self,self.mainwin.toggle)
                self.mainwin.window.show()
                #self.mainwin.wTree.get_object( 'PluginTabs' ).set_curremenu_editor = SetGconf( self.client, "string", "/apps/usp/menu_editor", "mozo" )
        except Exception, cause:
            print cause

    def enter_notify(self, applet, event):
        self.do_image(self.buttonIcon, True)

    def leave_notify(self, applet, event):
        self.do_image(self.buttonIcon, False)

    def do_image(self, image_file, saturate):
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(image_file)
        if saturate:
            GdkPixbuf.Pixbuf.saturate_and_pixelate(pixbuf, pixbuf, 1.5, False)
        self.button_icon.set_from_pixbuf(pixbuf)

    def createPanelButton( self ):
        self.button_icon = Gtk.image_new_from_file( self.buttonIcon )
        self.systemlabel = Gtk.Label(label= self.buttonText )
        if os.path.exists("/etc/linuxmint/info"):
            import commands
            tooltip = commands.getoutput("cat /etc/linuxmint/info | grep DESCRIPTION")
            tooltip = tooltip.replace("DESCRIPTION", "")
            tooltip = tooltip.replace("=", "")
            tooltip = tooltip.replace("\"", "")
            self.systemlabel.set_tooltip_text(tooltip)
            self.button_icon.set_tooltip_text(tooltip)

        if self.applet.get_orient() == mateapplet.ORIENT_UP or self.applet.get_orient() == mateapplet.ORIENT_DOWN:
            self.button_box = Gtk.HBox()
            self.button_box.pack_start( self.button_icon, False, False )
            self.button_box.pack_start( self.systemlabel, False, False )

            self.button_icon.set_padding( 5, 0 )
        # if we have a vertical panel
        elif self.applet.get_orient() == mateapplet.ORIENT_LEFT:
            self.button_box = Gtk.VBox()
            self.systemlabel.set_angle( 270 )
            self.button_box.pack_start( self.systemlabel , True, True, 0)
            self.button_box.pack_start( self.button_icon , True, True, 0)
            self.button_icon.set_padding( 5, 0 )
        elif self.applet.get_orient() == mateapplet.ORIENT_RIGHT:
            self.button_box = Gtk.VBox()
            self.systemlabel.set_angle( 90 )
            self.button_box.pack_start( self.button_icon , True, True, 0)
            self.button_box.pack_start( self.systemlabel , True, True, 0)
            self.button_icon.set_padding( 0, 5 )

        self.button_box.set_homogeneous( False )
        self.button_box.show_all()
        self.sizeButton()

        self.applet.add( self.button_box )


    def getGconfEntries( self, *args, **kargs ):
        self.hideIcon   =  self.gconf.get( "bool", "hide_applet_icon", False )
        self.buttonText =  self.gconf.get( "string", "applet_text", "Menu" )
        self.theme_name =  self.gconf.get( "string", "theme_name", "default" )
        self.hotkeyText =  self.gconf.get( "string", "hot_key", "<Control>Super_L" )
        self.buttonIcon =  self.gconf.get( "string", "applet_icon", ICON )
        self.iconSize = self.gconf.get( "int", "applet_icon_size", 22 )    

    def changeBackground( self, applet, type, color, pixmap ):
        
        self.applyTheme()
        
        # get reset style
        self.applet.set_style(None)
        rc_style = Gtk.RcStyle()
        self.applet.modify_style(rc_style)

        if mateapplet.COLOR_BACKGROUND == type:
            applet.modify_bg( Gtk.StateType.NORMAL, color )
        elif mateapplet.PIXMAP_BACKGROUND == type:
            style = applet.style
            style.bg_pixmap[ Gtk.StateType.NORMAL ] = pixmap
            applet.set_style( style )
            
    def changeTheme(self, *args):        
        self.gconfEntriesChanged()
        self.applyTheme()
        self.mainwin.RegenPlugins()
    
    def applyTheme(self):
        style_settings = Gtk.Settings.get_default()
        desktop_theme = self.gconf.get( "string", '/desktop/mate/interface/gtk_theme', "")
        if self.theme_name == "default":
            style_settings.set_property("gtk-theme-name", desktop_theme)        
        else:
            try:
                style_settings.set_property("gtk-theme-name", self.theme_name)
            except:
                style_settings.set_property("gtk-theme-name", desktop_theme)            

    def changeOrientation( self, *args, **kargs ):

        if self.applet.get_orient() == mateapplet.ORIENT_UP or self.applet.get_orient() == mateapplet.ORIENT_DOWN:
            tmpbox = Gtk.HBox()
            self.systemlabel.set_angle( 0 )
            self.button_box.reorder_child( self.button_icon, 0 )
            self.button_icon.set_padding( 5, 0 )
        elif self.applet.get_orient() == mateapplet.ORIENT_LEFT:
            tmpbox = Gtk.VBox()
            self.systemlabel.set_angle( 270 )
            self.button_box.reorder_child( self.button_icon, 1 )
            self.button_icon.set_padding( 0, 5 )
        elif self.applet.get_orient() == mateapplet.ORIENT_RIGHT:
            tmpbox = Gtk.VBox()
            self.systemlabel.set_angle( 90 )
            self.button_box.reorder_child( self.button_icon, 0 )
            self.button_icon.set_padding( 0, 5 )

        tmpbox.set_homogeneous( False )

        # reparent all the hboxes to the new tmpbox
        for i in self.button_box:
            i.reparent( tmpbox )

        self.button_box.destroy()

        self.button_box = tmpbox
        self.button_box.show()

        # this call makes sure width stays intact
        self.updateButton()
        self.applet.add( self.button_box )


    def updateButton( self ):
        self.systemlabel.set_text( self.buttonText )
        self.button_icon.clear()
        self.button_icon.set_from_file( self.buttonIcon )
        self.sizeButton()

    def bind_hot_key (self):
        try:
            # Binding menu to hotkey
            print "Binding to Hot Key: " + self.hotkeyText
            bind_key( self.hotkeyText, self.onBindingPress )
        except Exception, cause:
            print "** WARNING ** - Menu Hotkey Binding Error"
            print "Error Report :\n", str(cause)
            pass

    def sizeButton( self ):
        if self.hideIcon:
            self.button_icon.hide()
        else:
            self.button_icon.show()
        # This code calculates width and height for the button_box
        # and takes the orientation in account
        if self.applet.get_orient() == mateapplet.ORIENT_UP or self.applet.get_orient() == mateapplet.ORIENT_DOWN:
            if self.hideIcon:
                self.applet.set_size_request( self.systemlabel.size_request()[0] + 2, -1 )
            else:
                self.applet.set_size_request( self.systemlabel.size_request()[0] + self.button_icon.size_request()[0] + 5, self.button_icon.size_request()[1] )
        else:
            if self.hideIcon:
                self.applet.set_size_request( self.button_icon.size_request()[0], self.systemlabel.size_request()[1] + 2 )
            else:
                self.applet.set_size_request( self.button_icon.size_request()[0], self.systemlabel.size_request()[1] + self.button_icon.size_request()[1] + 5 )

    def gconfEntriesChanged( self, *args ):
        self.getGconfEntries()
        self.updateButton()        

    def showAboutDialog( self, uicomponent, verb ):

        Gtk.about_dialog_set_email_hook( lambda dialog, mail: gnomevfs.url_show( "mailto:" + mail ) )
        Gtk.about_dialog_set_url_hook( lambda dialog, url: gnomevfs.url_show( url ) )
        about = Gtk.AboutDialog()
        about.set_name("mintMenu")
        import commands
        version = commands.getoutput("/usr/lib/linuxmint/common/version.py mintmenu")
        about.set_version(version)
        try:
            h = open('/usr/share/common-licenses/GPL','r')
            s = h.readlines()
            gpl = ""
            for line in s:
                gpl += line
            h.close()
            about.set_license(gpl)
        except Exception, detail:
            print detail
        about.set_comments( _("Advanced Gnome Menu") )
        about.set_authors( ["Clement Lefebvre <clem@linuxmint.com>", "Lars-Peter Clausen <lars@laprican.de>"] )
        about.set_translator_credits(("translator-credits") )
        #about.set_copyright( _("Based on USP from S.Chanderbally") )
        about.set_logo( GdkPixbuf.Pixbuf.new_from_file("/usr/lib/linuxmint/mintMenu/icon.svg") )
        about.connect( "response", lambda dialog, r: dialog.destroy() )
        about.show()


    def showPreferences( self, uicomponent, verb ):
        #Execute( "mateconf-editor /apps/mintMenu" )
        Execute( os.path.join( PATH, "mintMenuConfig.py" ) )

    def showMenuEditor( self, uicomponent, verb ):
        Execute( "mozo" )

    def showMenu( self, widget=None, event=None ):
        if event == None or event.button == 1:
            self.toggleMenu()
        # show right click menu
        elif event.button == 3:
            self.create_menu()
        # allow middle click and drag
        elif event.button == 2:
            self.mainwin.hide( True )

    def toggleMenu( self ):
        if self.applet.state & Gtk.StateType.SELECTED:
            self.mainwin.hide( True )
        else:
            self.positionMenu()
            self.mainwin.show()
            self.wakePlugins()

    def wakePlugins( self ):
        self.mainwin.wakePlugins()

    def positionMenu( self ):
        # Get our own dimensions & position
        ourWidth  = self.mainwin.window.get_size()[0]
        ourHeight = self.mainwin.window.get_size()[1] + self.mainwin.offset

        # Get the dimensions/position of the widgetToAlignWith
        entryX, entryY = self.applet.window.get_origin()
        entryWidth, entryHeight =  self.applet.get_allocation().width, self.applet.get_allocation().height
        entryHeight = entryHeight + self.mainwin.offset

        # Get the screen dimensions
        screenHeight = Gdk.Screen.height()
        screenWidth = Gdk.Screen.width()

        if self.applet.get_orient() == mateapplet.ORIENT_UP or self.applet.get_orient() == mateapplet.ORIENT_DOWN:
            if entryX + ourWidth < screenWidth or  entryX + entryWidth / 2 < screenWidth / 2:
            # Align to the left of the entry
                newX = entryX
            else:
                # Align to the right of the entry
                newX = entryX + entryWidth - ourWidth

            if entryY + entryHeight / 2 < screenHeight / 2:
                # Align to the bottom of the entry
                newY = entryY + entryHeight
            else:
                newY = entryY - ourHeight
        else:
            if entryX + entryWidth / 2 < screenWidth / 2:
                # Align to the left of the entry
                newX = entryX + entryWidth
            else:
                # Align to the right of the entry
                newX = entryX - ourWidth

            if entryY + ourHeight < screenHeight or entryY + entryHeight / 2 < screenHeight / 2:
                # Align to the bottom of the entry
                newY = entryY
            else:
                newY = entryY - ourHeight + entryHeight
        # -"Move window"
        self.mainwin.window.move( newX, newY )

    # this callback is to create a context menu
    def create_menu(self):
        self.applet.setup_menu(self.propxml, self.verbs, None)

def menu_factory( applet, iid ):
    MenuWin( applet, iid )
    applet.show()
    return True

if len(sys.argv) == 2 and sys.argv[1] == "run-in-window":
    Gdk.threads_init()
    main_window = Gtk.Window( Gtk.WindowType.TOPLEVEL )
    main_window.set_title( NAME )
    app = mateapplet.Applet()
    menu_factory( app, None )
    app.reparent( main_window )
    main_window.show()
    Gdk.threads_enter()
    Gtk.main()
    Gdk.threads_leave()
else:
    mateapplet.matecomponent_factory("OAFIID:MATE_mintMenu_Factory",
                         mateapplet.Applet.__gtype__,
                         "mintMenu", "0", menu_factory)

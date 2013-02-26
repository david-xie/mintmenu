#!/usr/bin/env python
import gi
gi.require_version("Gtk", "2.0")

try:
    import sys
    import os
    import commands
    import threading
    import tempfile
    import gettext
    from gi.repository import Gtk
    from gi.repository import Gdk
    from gi.repository import GObject
except Exception, e:
    print e
    sys.exit(1)

from subprocess import Popen, PIPE

MINT_REMOVE_GLADE = "/usr/lib/linuxmint/mintMenu/mintRemove.glade"

GObject.threads_init()

# i18n
gettext.install("mintmenu", "/usr/share/linuxmint/locale")

class RemoveExecuter(threading.Thread):

    def __init__(self, window_id, package):
        threading.Thread.__init__(self)
        self.window_id = window_id
        self.package = package

    def execute(self, command):
        #print "Executing: " + command
        os.system(command)
        ret = commands.getoutput("echo $?")
        return ret

    def run(self):  
        removePackages = self.package.split()
        cmd = ["sudo", "/usr/sbin/synaptic", "--hide-main-window",  \
                "--non-interactive", "--parent-window-id", self.window_id]
        cmd.append("--progress-str")
        cmd.append("\"" + _("Please wait, this can take some time") + "\"")
        cmd.append("--finish-str")
        cmd.append("\"" + _("Application removed successfully") + "\"")
        f = tempfile.NamedTemporaryFile()
        for pkg in removePackages:
            f.write("%s\tdeinstall\n" % pkg)
            cmd.append("--set-selections-file")
            cmd.append("%s" % f.name)
            f.flush()
        comnd = Popen(' '.join(cmd), shell=True)
        returnCode = comnd.wait()
        f.close()
        Gtk.main_quit()
        sys.exit(0)


class Handler(object):
    def __init__(self, builder, window_id, package):
        self.builder = builder
        self.window_id = window_id
        self.package = package

    def on_cancel_button_clicked(self, *args):
        Gtk.main_quit()

    def on_remove_button_clicked(self, button):
        self.builder.get_object("main_window").window.set_cursor(Gdk.Cursor.new(Gdk.CursorType.WATCH))
        self.builder.get_object("main_window").set_sensitive(False)
        RemoveExecuter(self.window_id, self.package).start()
        return True


class MintRemoveWindow:

    def __init__(self, desktopFile):
        self.desktopFile = desktopFile
        self.builder = Gtk.Builder()
        self.builder.add_from_file(MINT_REMOVE_GLADE)
        self.builder.get_object("main_window").set_icon_from_file("/usr/lib/linuxmint/mintMenu/icon.svg")
        self.builder.get_object("main_window").set_title("")
        self.builder.get_object("main_window").connect("destroy", Gtk.main_quit)

        # Get the window socket (needed for synaptic later on)
        vbox = self.builder.get_object("vbox1")
        socket = Gtk.Socket()
        vbox.pack_start(socket, True, True, 0)
        socket.show()
        window_id = repr(socket.get_id())

        package = commands.getoutput("dpkg -S " + self.desktopFile)
        package = package[:package.find(":")]
        if package == "dpkg":
            warnDlg = Gtk.Dialog(title="MintMenu", parent=None, flags=0, buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL))
            warnDlg.add_button(Gtk.STOCK_REMOVE, Gtk.ResponseType.OK)
            warnDlg.vbox.set_spacing(10)
            warnDlg.set_icon_from_file("/usr/share/linuxmint/logo.png")
            labelSpc = Gtk.Label(label=" ")
            warnDlg.vbox.pack_start(labelSpc, True, True, 0)    
            labelSpc.show()
            warnText = "<b>" + _("No matching package found") + "</b>"
            infoText = _("Do you want to remove this menu entry?") + " (" + self.desktopFile + ")"
            label = Gtk.Label(label=warnText)
            lblInfo = Gtk.Label(label=infoText)
            label.set_use_markup(True)
            lblInfo.set_use_markup(True)
            warnDlg.vbox.pack_start(label, True, True, 0)
            warnDlg.vbox.pack_start(lblInfo, True, True, 0)
            label.show()
            lblInfo.show()
            response = warnDlg.run()
            if response == Gtk.ResponseType.OK :
                print "removing " + self.desktopFile + "*.desktop"
                os.system("rm -f " + self.desktopFile)
                os.system("rm -f " + self.desktopFile + "*.desktop")
            warnDlg.destroy()
            Gtk.main_quit()
            sys.exit(0)

        self.builder.get_object("txt_name").set_text("<big><b>" + _("Remove %s?") % package + "</b></big>")
        self.builder.get_object("txt_name").set_use_markup(True)

        self.builder.get_object("txt_guidance").set_text(_("The following packages will be removed:"))

        treeview = self.builder.get_object("tree")
        column1 = Gtk.TreeViewColumn(_("Packages to be removed"))
        renderer = Gtk.CellRendererText()
        column1.pack_start(renderer, False)
        #column1.set_attributes(renderer, text = 0)
        treeview.append_column(column1)

        model = Gtk.ListStore(str)
        dependenciesString = commands.getoutput("apt-get -s -q remove " + package + " | grep Remv")
        dependencies = dependenciesString.split("\n")
        for dependency in dependencies:
            dependency = dependency.replace("Remv ", "")
            model.append([dependency])
        treeview.set_model(model)
        treeview.show()

        self.builder.connect_signals(Handler(self.builder, window_id, package))
        self.builder.get_object("main_window").show()


if __name__ == "__main__":
    mint_remove_window = MintRemoveWindow(sys.argv[1])
    Gtk.main()


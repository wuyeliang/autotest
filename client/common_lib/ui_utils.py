import time
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils


class UI_Handler(object):

    REGEX_ALL = '/(.*?)/'

    def start_ui_root(self, cr):
        """Starts the UI root object for testing."""
        self.ext = cr.autotest_ext
        self.ext.ExecuteJavaScript("""
                var root;
                chrome.automation.getDesktop(r => root = r);
            """)

        # Currently need to wait a second to let the root object finish setup.
        time.sleep(1)

    def is_obj_restricted(self, name, isRegex=False, role=None):
        """

        Returns True if the object restriction is 'disabled'.
        This usually means the button is either greyed out, locked, etc.

        @param name: Parameter to provide to the 'name' attribute.
        @param isRegex: bool, if the item is a regex.
        @param role: Parameter to provide to the 'role' attribute.

         """
        self._set_obj_var(name, isRegex, role)

        try:
            restriction = self.ext.EvaluateJavaScript("""
                tempVar.restriction;""")
        except Exception:
            raise error.TestError(
                'Could not find object {}.'.format(name))

        if restriction == 'disabled':
            return True
        return False

    def item_present(self, name, isRegex=False, flip=False, role=None):
        """
        Determines if an object is present on the screen

        @param name: Parameter to provide to the 'name' attribute.
        @param isRegex: bool, if the 'name' is a regex.
        @param flip: Flips the return status.
        @param role: Parameter to provide to the 'role' attribute.

        @returns:
            True if object is present and flip is False.
            False if object is present and flip is True.
            False if object is not present and flip is False.
            True if object is not present and flip is True.

        """
        self._set_obj_var(name, isRegex, role)
        item = self.ext.EvaluateJavaScript("tempVar;")

        if item is None:
            return False if not flip else True
        return True if not flip else False

    def wait_for_ui_obj(self, name, isRegex=False, remove=False, role=None):
        """
        Waits for the UI object specified.

        @param name: Parameter to provide to the 'name' attribute.
        @param isRegex: bool, if the 'name' is a regex.
        @param remove: bool, if wait for the item to be removed.
        @param role: Parameter to provide to the 'role' attribute.

        @raises error.TestError if the element is not loaded (or removed).

        """
        utils.poll_for_condition(
            condition=lambda: self.item_present(name=name,
                                                isRegex=isRegex,
                                                flip=remove,
                                                role=role),
            timeout=10,
            exception=error.TestError('{} did not load'.format(name)))

    def did_obj_not_load(self, name, isRegex=False, timeout=5):
        """
        Specifically used to wait and see if an item appears on the UI.

        NOTE: This is different from wait_for_ui_obj because that returns as
        soon as the object is either loaded or not loaded. This function will
        wait to ensure over the timeout period the object never loads.
        Additionally it will return as soon as it does load. Basically a fancy
        time.sleep()

        @param name: Parameter to provide to the 'name' attribute.
        @param isRegex: bool, if the item is a regex.
        @param timeout: Time in seconds to wait for the object to appear.

        @returns: True if object never loaded within the timeout period,
            else False.

        """
        t1 = time.time()
        while time.time() - t1 < timeout:
            if self.item_present(name=name, isRegex=isRegex):
                return False
            time.sleep(1)
        return True

    def doDefault_on_obj(self, name, isRegex=False, role=None):
        """Runs the .doDefault() js command on the element."""
        self._set_obj_var(name, isRegex, role)
        self.ext.EvaluateJavaScript("tempVar.doDefault();")

    def doCommand_on_obj(self, name, cmd, isRegex=False, role=None):
        """Runs the specified command on the element."""
        self._set_obj_var(name, isRegex, role)
        return self.ext.EvaluateJavaScript("tempVar.{};".format(cmd))

    def list_screen_items(self,
                          role=None,
                          name=None,
                          isRegex=False,
                          attr='name'):

        """
        Lists all the items currently visable on the screen.

        If no paramters are given, it will return the name of each item,
        including items with empty names.

        @param role: The role of the items to use (ie button).
        @param name: Parameter to provide to the 'name' attribute.
        @param isRegex: bool, if the obj is a regex.
        @param attr: Str, the attribute you want returned in the list
            (eg 'name').

        """

        if isRegex:
            if name is None:
                raise error.TestError('If regex is True name must be given')
            name = self._format_obj(name, isRegex)
        name = self.REGEX_ALL if name is None else name
        role = self.REGEX_ALL if role is None else self._format_obj(role, False)

        return self.ext.EvaluateJavaScript('''
                root.findAll({attributes:
                    {name: %s, role: %s}}).map(node => node.%s);'''
                % (name, role, attr))

    def get_name_role_list(self):
        """
        Returns a list of dicts containing the name/role of everything
        on the screen.

        """
        combined = []
        names = self.list_screen_items(attr='name')
        roles = self.list_screen_items(attr='role')

        if len(names) != len(roles):
            raise error.TestError('Number of items in names and roles !=')

        for name, role in zip(names, roles):
            temp_d = {'name': name, 'role': role}
            combined.append(temp_d)
        return combined

    def _format_obj(self, name, isRegex):
        """
        Formats the object for use in the javascript name attribute.

        When searching for an element on the UI, a regex expression or string
        can be used. If the search is using a string, the obj will need to be
        wrapped in quotes. A Regex is not.

        @param name: Parameter to provide to the 'name' attribute.
        @param isRegex: if True, the object will be returned as is, if False
            the obj will be returned wrapped in quotes.

        @returns: The formatted string for regex/name.
        """
        if isRegex:
            return name
        else:
            return '"{}"'.format(name)

    def _set_obj_var(self, name, isRegex, role):
        """Sets a variable within the extension to be used later."""
        name = self._format_obj(name, isRegex)
        if role is None:
            role = self.REGEX_ALL
        else:
            role = self._format_obj(role, False)

        self.ext.EvaluateJavaScript("""
            var tempVar;
            tempVar = root.find({attributes:
                {name: %s,
                 role: %s}}
             );""" % (name, role))

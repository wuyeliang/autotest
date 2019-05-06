import time
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils


class UI_Handler(object):

    def start_ui_root(self, cr):
        """Starts the UI root object for testing."""
        self.ext = cr.autotest_ext
        self.ext.ExecuteJavaScript("""
                var root;
                chrome.automation.getDesktop(r => root = r);
            """)

        # Currently need to wait a second to let the root object finish setup.
        time.sleep(1)

    def is_obj_restricted(self, obj, isRegex=False, role=None):
        """

        Returns True if the object restriction is 'disabled'.
        This usually means the button is either greyed out, locked, etc.

        @param obj: the name/regex of the element.
        @param isRegex: bool, if the item is a regex. If item is str leave this
            as default.

         """
        self._set_obj_var(obj, isRegex, role)

        try:
            restriction = self.ext.EvaluateJavaScript("""
                tempVar.restriction;""")
        except Exception:
            raise error.TestError(
                'Could not find object {}.'.format(obj))

        if restriction == 'disabled':
            return True
        return False

    def item_present(self, element, isRegex=False, flip=False, role=None):
        """
        Determines if an object is present on the screen

        @param element: The element to look for.
        @param isRegex: bool, if the item is a regex. If item is str leave this
            as default.
        @param flip: Flips the return status.
        @param role: the role attribute of the element.

        @returns:
            True if object is present and flip is False.
            False if object is present and flip is True.
            False if object is not present and flip is False.
            True if object is not present and flip is True.

        """
        self._set_obj_var(element, isRegex, role)
        item = self.ext.EvaluateJavaScript("tempVar;")

        if item is None:
            return False if not flip else True
        return True if not flip else False

    def wait_for_ui_obj(self, element, isRegex=False, remove=False, role=None):
        """
        Waits for the UI object specified.

        @param element: The element to look for.
        @param isRegex: bool, if the item is a regex. If item is str leave this
            as default.
        @param remove: bool, if wait for the item to be removed.
        @param role: the role attribute of the element.
        @raises error.TestError if the element is not loaded (or removed).

        """
        utils.poll_for_condition(
            condition=lambda: self.item_present(element=element,
                                                isRegex=isRegex,
                                                flip=remove,
                                                role=role),
            timeout=10,
            exception=error.TestError('{} did not load'.format(element)))

    def did_obj_not_load(self, element, isRegex=False, timeout=5):
        """
        Specifically used to wait and see if an item appears on the UI.

        NOTE: This is different from wait_for_ui_obj because that returns as
        soon as the object is either loaded or not loaded. This function will
        wait to ensure over the timeout period the object never loads.
        Additionally it will return as soon as it does load. Basically a fancy
        time.sleep()

        @param element: The element to look for.
        @param isRegex: bool, if the item is a regex. If item is str leave this
            as default.
        @param timeout: Time in seconds to wait for the object to appear.

        @returns: True if object never loaded within the timeout period,
            else False.

        """
        t1 = time.time()
        while time.time() - t1 < timeout:
            if self.item_present(element=element, isRegex=isRegex):
                return False
            time.sleep(1)
        return True

    def doDefault_on_obj(self, obj, isRegex=False, role=None):
        """Runs the .doDefault() js command on the obj."""
        self._set_obj_var(obj, isRegex, role)
        self.ext.EvaluateJavaScript("tempVar.doDefault();")

    def doCommand_on_obj(self, obj, cmd, isRegex=False, role=None):
        """Runs the specified command on the obj."""
        self._set_obj_var(obj, isRegex, role)
        return self.ext.EvaluateJavaScript("tempVar.{};".format(cmd))

    def format_obj(self, obj, isRegex):
        """
        Formats the object for use in the javascript name attribute.

        When searching for an element on the UI, a regex expression or string
        can be used. If the search is using a string, the obj will need to be
        wrapped in quotes. A Regex is not.

        @param obj: the string of the object to be used in the name attribute.
        @param isRegex: if True, the object will be returned as is, is False
            the obj will be returned wrapped in quotes.

        """
        if isRegex:
            return obj
        else:
            return '"{}"'.format(obj)

    def _set_obj_var(self, obj, isRegex, role):
        obj = self.format_obj(obj, isRegex)
        if role is None:
            role = '/(.*?)/'
        else:
            role = self.format_obj(role, False)

        self.ext.EvaluateJavaScript("""
            var tempVar;
            tempVar = root.find({attributes:
                {name: %s,
                 role: %s}}
             );""" % (obj, role))

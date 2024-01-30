python early in autofocus:
    from renpy import store
    from store import Transform, _warper, config

    class Callbacks(object):
        def __init__(self, *callbacks):
            self.callbacks = callbacks
        
        def __call__(self, *args, **kwargs):
            for callback in self.callbacks:
                callback(*args, **kwargs)

    class Autofocus(renpy.Container, store.NoRollback):
        offset = [(0, 0)]

        def __init__(self, child, name, **kwargs):
            super(Autofocus, self).__init__(Transform(child, subpixel=True), **kwargs)            
            self.tag = name.split()[0]

        def render(self, width, height, st, at):
            self.child.zoom = _autofocus_map[self.tag].current

            renpy.redraw(self, 0.0)
            return renpy.render(self.child, width, height, st, at)

    store.AutofocusDisplayable = renpy.curry(Autofocus)

    class BaseAutofocusCallback(object):
        def __init__(self, name, begin_parameter, end_parameter):
            self.name = name
            self.begin_parameter = begin_parameter
            self.end_parameter = end_parameter
        
        def call(self, parameter):
            raise NotImplementedError("%s.call not implemented" % type(self).__name__)
        
        def __call__(self, event, interact=True, **kwargs):
            if not interact: return

            if event == "begin":
                self.call(self.begin_parameter)
            elif event == "end":
                self.call(self.end_parameter)

    class AutofocusZorder(BaseAutofocusCallback):
        def __init__(self, name, begin_parameter=3, end_parameter=2):
            super(AutofocusZorder, self).__init__(name, begin_parameter, end_parameter)

        def call(self, parameter):
            if not zorder: return
            layer = renpy.default_layer(None, self.name)
            renpy.change_zorder(layer, self.name, parameter)

    def Character(*args, **kwargs):
        autofocus = kwargs.pop("autofocus", True)

        image = kwargs.get("image", kwargs.get("kind", store.adv).image_tag)

        if autofocus and image:
            callbacks = [AutofocusZorder(image)]
            if "callback" in kwargs:
                callbacks.append(kwargs["callback"])

            kwargs["callback"] = Callbacks(*callbacks)

            if renpy.is_init_phase():
                config.start_callbacks.append(
                    lambda: _autofocus_map.setdefault(image, _AutofocusObject())
                )
                config.tag_zorder[image] = 2
            else:
                _autofocus_map.setdefault(image, _AutofocusObject())
        
        return renpy.character.Character(*args, **kwargs)

    store.Character = Character
    store.DynamicCharacter = renpy.partial(Character, dynamic=True)


    def block(tag):
        """
        Freezes the focus process.
        """
        _blocked.add(tag)
    
    def unblock(tag):
        """
        Unfreezes the focus process.
        """
        _blocked.discard(tag)
    
    def force_focus(tag):
        """
        Forces a character to be focused.
        """
        _force_focus.add(tag)
    
    def restore_focus(tag):
        """
        Restores normal focus.
        """
        _force_focus.discard(tag)

    # this absolute lasagna of a workaround
    import time

    FOCUSED = 1.05
    UNFOCUSED = 1.0
    DURATION = 0.2
    WARPER = _warper.easein

    class _AutofocusObject(object):
        def __init__(self):
            self.start_time = time.time()
            self.focused = False
            self.blocked = False
            self.current = UNFOCUSED
            self.previous = UNFOCUSED
            self.target = UNFOCUSED            

    renpy_display_scenelists = renpy.display.scenelists
    renpy_display_core = renpy.display.core

    layer_thing = renpy_display_scenelists if renpy.version_tuple >= ((7, 7) if renpy.compat.PY2 else (8, 2)) else renpy_display_core

    class _ComputeFocus(renpy.Displayable):
        def __init__(self, tag):
            super(_ComputeFocus, self).__init__()
            self.tag = tag

        def render(self, w, h, st, at):
            current_time = time.time()
            
            showing_tags = set()
            for layer in layer_thing.layers:
                showing_tags |= renpy.get_showing_tags(layer)

            tag = self.tag
            focus_object = _autofocus_map[tag]

            if tag in _blocked:
                focus_object.blocked = True
                return renpy.Render(0, 0)

            if focus_object.blocked:
                focus_object.blocked = False
                focus_object.start_time = current_time

            focused = (
                tag in showing_tags and
                (tag in _force_focus or renpy.get_say_image_tag() == tag)
            )

            if focused != focus_object.focused:
                focus_object.previous = focus_object.current
                focus_object.target = FOCUSED if focused else UNFOCUSED
                focus_object.start_time = current_time
                focus_object.focused = focused

            elapsed_time = (current_time - focus_object.start_time) * renpy_display_core.time_mult
            done = min(elapsed_time / DURATION, 1.0)

            focus_object.current = focus_object.previous + ((focus_object.target - focus_object.previous) * WARPER(done))

            return renpy.Render(0, 0)

    config.per_frame_screens.append("_compute_autofocus")
    config.always_shown_screens.append("_compute_autofocus")

screen _compute_autofocus():
    for t in autofocus._autofocus_map:
        add autofocus._ComputeFocus(t)

default autofocus._autofocus_map = { }
default autofocus._force_focus = set()
default autofocus._blocked = set()

default autofocus.zorder = True

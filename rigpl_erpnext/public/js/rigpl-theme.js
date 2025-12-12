! function(t) {
    "use strict";
    t = t && t.hasOwnProperty("default") ? t.default : t;
    var e = "undefined" != typeof window ? window : "undefined" != typeof global ? global : "undefined" != typeof self ? self : {};
    var n, i, o = (function(n, i) {
        ! function(t, n) {
            function i(t, e) {
                for (var n = 0; n < e.length; n++) {
                    var i = e[n];
                    i.enumerable = i.enumerable || !1, i.configurable = !0, "value" in i && (i.writable = !0), Object.defineProperty(t, i.key, i)
                }
            }

            function o(t, e, n) {
                return e && i(t.prototype, e), n && i(t, n), t
            }

            function r(t, e, n) {
                return e in t ? Object.defineProperty(t, e, {
                    value: n,
                    enumerable: !0,
                    configurable: !0,
                    writable: !0
                }) : t[e] = n, t
            }

            function s(t) {
                for (var e = arguments, n = 1; n < arguments.length; n++) {
                    var i = null != e[n] ? e[n] : {},
                        o = Object.keys(i);
                    "function" == typeof Object.getOwnPropertySymbols && (o = o.concat(Object.getOwnPropertySymbols(i).filter(function(t) {
                        return Object.getOwnPropertyDescriptor(i, t).enumerable
                    }))), o.forEach(function(e) {
                        r(t, e, i[e])
                    })
                }
                return t
            }
            n = n && n.hasOwnProperty("default") ? n.default : n;
            var a = "transitionend";

            function l(t) {
                var e = this,
                    i = !1;
                return n(this).one(c.TRANSITION_END, function() {
                    i = !0
                }), setTimeout(function() {
                    i || c.triggerTransitionEnd(e)
                }, t), this
            }
            var c = {
                TRANSITION_END: "bsTransitionEnd",
                getUID: function(t) {
                    do {
                        t += ~~(1e6 * Math.random())
                    } while (document.getElementById(t));
                    return t
                },
                getSelectorFromElement: function(t) {
                    var e = t.getAttribute("data-target");
                    if (!e || "#" === e) {
                        var n = t.getAttribute("href");
                        e = n && "#" !== n ? n.trim() : ""
                    }
                    try {
                        return document.querySelector(e) ? e : null
                    } catch (t) {
                        return null
                    }
                },
                getTransitionDurationFromElement: function(t) {
                    if (!t) return 0;
                    var e = n(t).css("transition-duration"),
                        i = n(t).css("transition-delay"),
                        o = parseFloat(e),
                        r = parseFloat(i);
                    return o || r ? (e = e.split(",")[0], i = i.split(",")[0], 1e3 * (parseFloat(e) + parseFloat(i))) : 0
                },
                reflow: function(t) {
                    return t.offsetHeight
                },
                triggerTransitionEnd: function(t) {
                    n(t).trigger(a)
                },
                supportsTransitionEnd: function() {
                    return Boolean(a)
                },
                isElement: function(t) {
                    return (t[0] || t).nodeType
                },
                typeCheckConfig: function(t, e, n) {
                    for (var i in n)
                        if (Object.prototype.hasOwnProperty.call(n, i)) {
                            var o = n[i],
                                r = e[i],
                                s = r && c.isElement(r) ? "element" : (a = r, {}.toString.call(a).match(/\s([a-z]+)/i)[1].toLowerCase());
                            if (!new RegExp(o).test(s)) throw new Error(t.toUpperCase() + ': Option "' + i + '" provided type "' + s + '" but expected type "' + o + '".')
                        }
                    var a
                },
                findShadowRoot: function(t) {
                    if (!document.documentElement.attachShadow) return null;
                    if ("function" == typeof t.getRootNode) {
                        var e = t.getRootNode();
                        return e instanceof ShadowRoot ? e : null
                    }
                    return t instanceof ShadowRoot ? t : t.parentNode ? c.findShadowRoot(t.parentNode) : null
                }
            };
            n.fn.emulateTransitionEnd = l, n.event.special[c.TRANSITION_END] = {
                bindType: a,
                delegateType: a,
                handle: function(t) {
                    if (n(t.target).is(this)) return t.handleObj.handler.apply(this, arguments)
                }
            };
            var u = n.fn.alert,
                h = {
                    CLOSE: "close.bs.alert",
                    CLOSED: "closed.bs.alert",
                    CLICK_DATA_API: "click.bs.alert.data-api"
                },
                f = {
                    ALERT: "alert",
                    FADE: "fade",
                    SHOW: "show"
                },
                d = function() {
                    function t(t) {
                        this._element = t
                    }
                    var e = t.prototype;
                    return e.close = function(t) {
                        var e = this._element;
                        t && (e = this._getRootElement(t));
                        var n = this._triggerCloseEvent(e);
                        n.isDefaultPrevented() || this._removeElement(e)
                    }, e.dispose = function() {
                        n.removeData(this._element, "bs.alert"), this._element = null
                    }, e._getRootElement = function(t) {
                        var e = c.getSelectorFromElement(t),
                            i = !1;
                        return e && (i = document.querySelector(e)), i || (i = n(t).closest("." + f.ALERT)[0]), i
                    }, e._triggerCloseEvent = function(t) {
                        var e = n.Event(h.CLOSE);
                        return n(t).trigger(e), e
                    }, e._removeElement = function(t) {
                        var e = this;
                        if (n(t).removeClass(f.SHOW), n(t).hasClass(f.FADE)) {
                            var i = c.getTransitionDurationFromElement(t);
                            n(t).one(c.TRANSITION_END, function(n) {
                                return e._destroyElement(t, n)
                            }).emulateTransitionEnd(i)
                        } else this._destroyElement(t)
                    }, e._destroyElement = function(t) {
                        n(t).detach().trigger(h.CLOSED).remove()
                    }, t._jQueryInterface = function(e) {
                        return this.each(function() {
                            var i = n(this),
                                o = i.data("bs.alert");
                            o || (o = new t(this), i.data("bs.alert", o)), "close" === e && o[e](this)
                        })
                    }, t._handleDismiss = function(t) {
                        return function(e) {
                            e && e.preventDefault(), t.close(this)
                        }
                    }, o(t, null, [{
                        key: "VERSION",
                        get: function() {
                            return "4.3.1"
                        }
                    }]), t
                }();
            n(document).on(h.CLICK_DATA_API, '[data-dismiss="alert"]', d._handleDismiss(new d)), n.fn.alert = d._jQueryInterface, n.fn.alert.Constructor = d, n.fn.alert.noConflict = function() {
                return n.fn.alert = u, d._jQueryInterface
            };
            var p = n.fn.button,
                m = {
                    ACTIVE: "active",
                    BUTTON: "btn",
                    FOCUS: "focus"
                },
                g = {
                    DATA_TOGGLE_CARROT: '[data-toggle^="button"]',
                    DATA_TOGGLE: '[data-toggle="buttons"]',
                    INPUT: 'input:not([type="hidden"])',
                    ACTIVE: ".active",
                    BUTTON: ".btn"
                },
                _ = {
                    CLICK_DATA_API: "click.bs.button.data-api",
                    FOCUS_BLUR_DATA_API: "focus.bs.button.data-api blur.bs.button.data-api"
                },
                v = function() {
                    function t(t) {
                        this._element = t
                    }
                    var e = t.prototype;
                    return e.toggle = function() {
                        var t = !0,
                            e = !0,
                            i = n(this._element).closest(g.DATA_TOGGLE)[0];
                        if (i) {
                            var o = this._element.querySelector(g.INPUT);
                            if (o) {
                                if ("radio" === o.type)
                                    if (o.checked && this._element.classList.contains(m.ACTIVE)) t = !1;
                                    else {
                                        var r = i.querySelector(g.ACTIVE);
                                        r && n(r).removeClass(m.ACTIVE)
                                    }
                                if (t) {
                                    if (o.hasAttribute("disabled") || i.hasAttribute("disabled") || o.classList.contains("disabled") || i.classList.contains("disabled")) return;
                                    o.checked = !this._element.classList.contains(m.ACTIVE), n(o).trigger("change")
                                }
                                o.focus(), e = !1
                            }
                        }
                        e && this._element.setAttribute("aria-pressed", !this._element.classList.contains(m.ACTIVE)), t && n(this._element).toggleClass(m.ACTIVE)
                    }, e.dispose = function() {
                        n.removeData(this._element, "bs.button"), this._element = null
                    }, t._jQueryInterface = function(e) {
                        return this.each(function() {
                            var i = n(this).data("bs.button");
                            i || (i = new t(this), n(this).data("bs.button", i)), "toggle" === e && i[e]()
                        })
                    }, o(t, null, [{
                        key: "VERSION",
                        get: function() {
                            return "4.3.1"
                        }
                    }]), t
                }();
            n(document).on(_.CLICK_DATA_API, g.DATA_TOGGLE_CARROT, function(t) {
                t.preventDefault();
                var e = t.target;
                n(e).hasClass(m.BUTTON) || (e = n(e).closest(g.BUTTON)), v._jQueryInterface.call(n(e), "toggle")
            }).on(_.FOCUS_BLUR_DATA_API, g.DATA_TOGGLE_CARROT, function(t) {
                var e = n(t.target).closest(g.BUTTON)[0];
                n(e).toggleClass(m.FOCUS, /^focus(in)?$/.test(t.type))
            }), n.fn.button = v._jQueryInterface, n.fn.button.Constructor = v, n.fn.button.noConflict = function() {
                return n.fn.button = p, v._jQueryInterface
            };
            var E = "carousel",
                T = ".bs.carousel",
                b = n.fn[E],
                y = {
                    interval: 5e3,
                    keyboard: !0,
                    slide: !1,
                    pause: "hover",
                    wrap: !0,
                    touch: !0
                },
                S = {
                    interval: "(number|boolean)",
                    keyboard: "boolean",
                    slide: "(boolean|string)",
                    pause: "(string|boolean)",
                    wrap: "boolean",
                    touch: "boolean"
                },
                O = {
                    NEXT: "next",
                    PREV: "prev",
                    LEFT: "left",
                    RIGHT: "right"
                },
                I = {
                    SLIDE: "slide.bs.carousel",
                    SLID: "slid.bs.carousel",
                    KEYDOWN: "keydown.bs.carousel",
                    MOUSEENTER: "mouseenter.bs.carousel",
                    MOUSELEAVE: "mouseleave.bs.carousel",
                    TOUCHSTART: "touchstart.bs.carousel",
                    TOUCHMOVE: "touchmove.bs.carousel",
                    TOUCHEND: "touchend.bs.carousel",
                    POINTERDOWN: "pointerdown.bs.carousel",
                    POINTERUP: "pointerup.bs.carousel",
                    DRAG_START: "dragstart.bs.carousel",
                    LOAD_DATA_API: "load.bs.carousel.data-api",
                    CLICK_DATA_API: "click.bs.carousel.data-api"
                },
                C = {
                    CAROUSEL: "carousel",
                    ACTIVE: "active",
                    SLIDE: "slide",
                    RIGHT: "carousel-item-right",
                    LEFT: "carousel-item-left",
                    NEXT: "carousel-item-next",
                    PREV: "carousel-item-prev",
                    ITEM: "carousel-item",
                    POINTER_EVENT: "pointer-event"
                },
                A = {
                    ACTIVE: ".active",
                    ACTIVE_ITEM: ".active.carousel-item",
                    ITEM: ".carousel-item",
                    ITEM_IMG: ".carousel-item img",
                    NEXT_PREV: ".carousel-item-next, .carousel-item-prev",
                    INDICATORS: ".carousel-indicators",
                    DATA_SLIDE: "[data-slide], [data-slide-to]",
                    DATA_RIDE: '[data-ride="carousel"]'
                },
                D = {
                    TOUCH: "touch",
                    PEN: "pen"
                },
                w = function() {
                    function t(t, e) {
                        this._items = null, this._interval = null, this._activeElement = null, this._isPaused = !1, this._isSliding = !1, this.touchTimeout = null, this.touchStartX = 0, this.touchDeltaX = 0, this._config = this._getConfig(e), this._element = t, this._indicatorsElement = this._element.querySelector(A.INDICATORS), this._touchSupported = "ontouchstart" in document.documentElement || navigator.maxTouchPoints > 0, this._pointerEvent = Boolean(window.PointerEvent || window.MSPointerEvent), this._addEventListeners()
                    }
                    var e = t.prototype;
                    return e.next = function() {
                        this._isSliding || this._slide(O.NEXT)
                    }, e.nextWhenVisible = function() {
                        !document.hidden && n(this._element).is(":visible") && "hidden" !== n(this._element).css("visibility") && this.next()
                    }, e.prev = function() {
                        this._isSliding || this._slide(O.PREV)
                    }, e.pause = function(t) {
                        t || (this._isPaused = !0), this._element.querySelector(A.NEXT_PREV) && (c.triggerTransitionEnd(this._element), this.cycle(!0)), clearInterval(this._interval), this._interval = null
                    }, e.cycle = function(t) {
                        t || (this._isPaused = !1), this._interval && (clearInterval(this._interval), this._interval = null), this._config.interval && !this._isPaused && (this._interval = setInterval((document.visibilityState ? this.nextWhenVisible : this.next).bind(this), this._config.interval))
                    }, e.to = function(t) {
                        var e = this;
                        this._activeElement = this._element.querySelector(A.ACTIVE_ITEM);
                        var i = this._getItemIndex(this._activeElement);
                        if (!(t > this._items.length - 1 || t < 0))
                            if (this._isSliding) n(this._element).one(I.SLID, function() {
                                return e.to(t)
                            });
                            else {
                                if (i === t) return this.pause(), void this.cycle();
                                var o = t > i ? O.NEXT : O.PREV;
                                this._slide(o, this._items[t])
                            }
                    }, e.dispose = function() {
                        n(this._element).off(T), n.removeData(this._element, "bs.carousel"), this._items = null, this._config = null, this._element = null, this._interval = null, this._isPaused = null, this._isSliding = null, this._activeElement = null, this._indicatorsElement = null
                    }, e._getConfig = function(t) {
                        return t = s({}, y, t), c.typeCheckConfig(E, t, S), t
                    }, e._handleSwipe = function() {
                        var t = Math.abs(this.touchDeltaX);
                        if (!(t <= 40)) {
                            var e = t / this.touchDeltaX;
                            e > 0 && this.prev(), e < 0 && this.next()
                        }
                    }, e._addEventListeners = function() {
                        var t = this;
                        this._config.keyboard && n(this._element).on(I.KEYDOWN, function(e) {
                            return t._keydown(e)
                        }), "hover" === this._config.pause && n(this._element).on(I.MOUSEENTER, function(e) {
                            return t.pause(e)
                        }).on(I.MOUSELEAVE, function(e) {
                            return t.cycle(e)
                        }), this._config.touch && this._addTouchEventListeners()
                    }, e._addTouchEventListeners = function() {
                        var t = this;
                        if (this._touchSupported) {
                            var e = function(e) {
                                    t._pointerEvent && D[e.originalEvent.pointerType.toUpperCase()] ? t.touchStartX = e.originalEvent.clientX : t._pointerEvent || (t.touchStartX = e.originalEvent.touches[0].clientX)
                                },
                                i = function(e) {
                                    t._pointerEvent && D[e.originalEvent.pointerType.toUpperCase()] && (t.touchDeltaX = e.originalEvent.clientX - t.touchStartX), t._handleSwipe(), "hover" === t._config.pause && (t.pause(), t.touchTimeout && clearTimeout(t.touchTimeout), t.touchTimeout = setTimeout(function(e) {
                                        return t.cycle(e)
                                    }, 500 + t._config.interval))
                                };
                            n(this._element.querySelectorAll(A.ITEM_IMG)).on(I.DRAG_START, function(t) {
                                return t.preventDefault()
                            }), this._pointerEvent ? (n(this._element).on(I.POINTERDOWN, function(t) {
                                return e(t)
                            }), n(this._element).on(I.POINTERUP, function(t) {
                                return i(t)
                            }), this._element.classList.add(C.POINTER_EVENT)) : (n(this._element).on(I.TOUCHSTART, function(t) {
                                return e(t)
                            }), n(this._element).on(I.TOUCHMOVE, function(e) {
                                return function(e) {
                                    e.originalEvent.touches && e.originalEvent.touches.length > 1 ? t.touchDeltaX = 0 : t.touchDeltaX = e.originalEvent.touches[0].clientX - t.touchStartX
                                }(e)
                            }), n(this._element).on(I.TOUCHEND, function(t) {
                                return i(t)
                            }))
                        }
                    }, e._keydown = function(t) {
                        if (!/input|textarea/i.test(t.target.tagName)) switch (t.which) {
                            case 37:
                                t.preventDefault(), this.prev();
                                break;
                            case 39:
                                t.preventDefault(), this.next()
                        }
                    }, e._getItemIndex = function(t) {
                        return this._items = t && t.parentNode ? [].slice.call(t.parentNode.querySelectorAll(A.ITEM)) : [], this._items.indexOf(t)
                    }, e._getItemByDirection = function(t, e) {
                        var n = t === O.NEXT,
                            i = t === O.PREV,
                            o = this._getItemIndex(e),
                            r = this._items.length - 1,
                            s = i && 0 === o || n && o === r;
                        if (s && !this._config.wrap) return e;
                        var a = t === O.PREV ? -1 : 1,
                            l = (o + a) % this._items.length;
                        return -1 === l ? this._items[this._items.length - 1] : this._items[l]
                    }, e._triggerSlideEvent = function(t, e) {
                        var i = this._getItemIndex(t),
                            o = this._getItemIndex(this._element.querySelector(A.ACTIVE_ITEM)),
                            r = n.Event(I.SLIDE, {
                                relatedTarget: t,
                                direction: e,
                                from: o,
                                to: i
                            });
                        return n(this._element).trigger(r), r
                    }, e._setActiveIndicatorElement = function(t) {
                        if (this._indicatorsElement) {
                            var e = [].slice.call(this._indicatorsElement.querySelectorAll(A.ACTIVE));
                            n(e).removeClass(C.ACTIVE);
                            var i = this._indicatorsElement.children[this._getItemIndex(t)];
                            i && n(i).addClass(C.ACTIVE)
                        }
                    }, e._slide = function(t, e) {
                        var i, o, r, s = this,
                            a = this._element.querySelector(A.ACTIVE_ITEM),
                            l = this._getItemIndex(a),
                            u = e || a && this._getItemByDirection(t, a),
                            h = this._getItemIndex(u),
                            f = Boolean(this._interval);
                        if (t === O.NEXT ? (i = C.LEFT, o = C.NEXT, r = O.LEFT) : (i = C.RIGHT, o = C.PREV, r = O.RIGHT), u && n(u).hasClass(C.ACTIVE)) this._isSliding = !1;
                        else {
                            var d = this._triggerSlideEvent(u, r);
                            if (!d.isDefaultPrevented() && a && u) {
                                this._isSliding = !0, f && this.pause(), this._setActiveIndicatorElement(u);
                                var p = n.Event(I.SLID, {
                                    relatedTarget: u,
                                    direction: r,
                                    from: l,
                                    to: h
                                });
                                if (n(this._element).hasClass(C.SLIDE)) {
                                    n(u).addClass(o), c.reflow(u), n(a).addClass(i), n(u).addClass(i);
                                    var m = parseInt(u.getAttribute("data-interval"), 10);
                                    m ? (this._config.defaultInterval = this._config.defaultInterval || this._config.interval, this._config.interval = m) : this._config.interval = this._config.defaultInterval || this._config.interval;
                                    var g = c.getTransitionDurationFromElement(a);
                                    n(a).one(c.TRANSITION_END, function() {
                                        n(u).removeClass(i + " " + o).addClass(C.ACTIVE), n(a).removeClass(C.ACTIVE + " " + o + " " + i), s._isSliding = !1, setTimeout(function() {
                                            return n(s._element).trigger(p)
                                        }, 0)
                                    }).emulateTransitionEnd(g)
                                } else n(a).removeClass(C.ACTIVE), n(u).addClass(C.ACTIVE), this._isSliding = !1, n(this._element).trigger(p);
                                f && this.cycle()
                            }
                        }
                    }, t._jQueryInterface = function(e) {
                        return this.each(function() {
                            var i = n(this).data("bs.carousel"),
                                o = s({}, y, n(this).data());
                            "object" == typeof e && (o = s({}, o, e));
                            var r = "string" == typeof e ? e : o.slide;
                            if (i || (i = new t(this, o), n(this).data("bs.carousel", i)), "number" == typeof e) i.to(e);
                            else if ("string" == typeof r) {
                                if (void 0 === i[r]) throw new TypeError('No method named "' + r + '"');
                                i[r]()
                            } else o.interval && o.ride && (i.pause(), i.cycle())
                        })
                    }, t._dataApiClickHandler = function(e) {
                        var i = c.getSelectorFromElement(this);
                        if (i) {
                            var o = n(i)[0];
                            if (o && n(o).hasClass(C.CAROUSEL)) {
                                var r = s({}, n(o).data(), n(this).data()),
                                    a = this.getAttribute("data-slide-to");
                                a && (r.interval = !1), t._jQueryInterface.call(n(o), r), a && n(o).data("bs.carousel").to(a), e.preventDefault()
                            }
                        }
                    }, o(t, null, [{
                        key: "VERSION",
                        get: function() {
                            return "4.3.1"
                        }
                    }, {
                        key: "Default",
                        get: function() {
                            return y
                        }
                    }]), t
                }();
            n(document).on(I.CLICK_DATA_API, A.DATA_SLIDE, w._dataApiClickHandler), n(window).on(I.LOAD_DATA_API, function() {
                for (var t = [].slice.call(document.querySelectorAll(A.DATA_RIDE)), e = 0, i = t.length; e < i; e++) {
                    var o = n(t[e]);
                    w._jQueryInterface.call(o, o.data())
                }
            }), n.fn[E] = w._jQueryInterface, n.fn[E].Constructor = w, n.fn[E].noConflict = function() {
                return n.fn[E] = b, w._jQueryInterface
            };
            var N = "collapse",
                L = n.fn[N],
                P = {
                    toggle: !0,
                    parent: ""
                },
                H = {
                    toggle: "boolean",
                    parent: "(string|element)"
                },
                R = {
                    SHOW: "show.bs.collapse",
                    SHOWN: "shown.bs.collapse",
                    HIDE: "hide.bs.collapse",
                    HIDDEN: "hidden.bs.collapse",
                    CLICK_DATA_API: "click.bs.collapse.data-api"
                },
                W = {
                    SHOW: "show",
                    COLLAPSE: "collapse",
                    COLLAPSING: "collapsing",
                    COLLAPSED: "collapsed"
                },
                k = {
                    WIDTH: "width",
                    HEIGHT: "height"
                },
                F = {
                    ACTIVES: ".show, .collapsing",
                    DATA_TOGGLE: '[data-toggle="collapse"]'
                },
                M = function() {
                    function t(t, e) {
                        this._isTransitioning = !1, this._element = t, this._config = this._getConfig(e), this._triggerArray = [].slice.call(document.querySelectorAll('[data-toggle="collapse"][href="#' + t.id + '"],[data-toggle="collapse"][data-target="#' + t.id + '"]'));
                        for (var n = [].slice.call(document.querySelectorAll(F.DATA_TOGGLE)), i = 0, o = n.length; i < o; i++) {
                            var r = n[i],
                                s = c.getSelectorFromElement(r),
                                a = [].slice.call(document.querySelectorAll(s)).filter(function(e) {
                                    return e === t
                                });
                            null !== s && a.length > 0 && (this._selector = s, this._triggerArray.push(r))
                        }
                        this._parent = this._config.parent ? this._getParent() : null, this._config.parent || this._addAriaAndCollapsedClass(this._element, this._triggerArray), this._config.toggle && this.toggle()
                    }
                    var e = t.prototype;
                    return e.toggle = function() {
                        n(this._element).hasClass(W.SHOW) ? this.hide() : this.show()
                    }, e.show = function() {
                        var e, i, o = this;
                        if (!(this._isTransitioning || n(this._element).hasClass(W.SHOW) || (this._parent && 0 === (e = [].slice.call(this._parent.querySelectorAll(F.ACTIVES)).filter(function(t) {
                                return "string" == typeof o._config.parent ? t.getAttribute("data-parent") === o._config.parent : t.classList.contains(W.COLLAPSE)
                            })).length && (e = null), e && (i = n(e).not(this._selector).data("bs.collapse")) && i._isTransitioning))) {
                            var r = n.Event(R.SHOW);
                            if (n(this._element).trigger(r), !r.isDefaultPrevented()) {
                                e && (t._jQueryInterface.call(n(e).not(this._selector), "hide"), i || n(e).data("bs.collapse", null));
                                var s = this._getDimension();
                                n(this._element).removeClass(W.COLLAPSE).addClass(W.COLLAPSING), this._element.style[s] = 0, this._triggerArray.length && n(this._triggerArray).removeClass(W.COLLAPSED).attr("aria-expanded", !0), this.setTransitioning(!0);
                                var a = s[0].toUpperCase() + s.slice(1),
                                    l = "scroll" + a,
                                    u = c.getTransitionDurationFromElement(this._element);
                                n(this._element).one(c.TRANSITION_END, function() {
                                    n(o._element).removeClass(W.COLLAPSING).addClass(W.COLLAPSE).addClass(W.SHOW), o._element.style[s] = "", o.setTransitioning(!1), n(o._element).trigger(R.SHOWN)
                                }).emulateTransitionEnd(u), this._element.style[s] = this._element[l] + "px"
                            }
                        }
                    }, e.hide = function() {
                        var t = this;
                        if (!this._isTransitioning && n(this._element).hasClass(W.SHOW)) {
                            var e = n.Event(R.HIDE);
                            if (n(this._element).trigger(e), !e.isDefaultPrevented()) {
                                var i = this._getDimension();
                                this._element.style[i] = this._element.getBoundingClientRect()[i] + "px", c.reflow(this._element), n(this._element).addClass(W.COLLAPSING).removeClass(W.COLLAPSE).removeClass(W.SHOW);
                                var o = this._triggerArray.length;
                                if (o > 0)
                                    for (var r = 0; r < o; r++) {
                                        var s = this._triggerArray[r],
                                            a = c.getSelectorFromElement(s);
                                        if (null !== a) {
                                            var l = n([].slice.call(document.querySelectorAll(a)));
                                            l.hasClass(W.SHOW) || n(s).addClass(W.COLLAPSED).attr("aria-expanded", !1)
                                        }
                                    }
                                this.setTransitioning(!0), this._element.style[i] = "";
                                var u = c.getTransitionDurationFromElement(this._element);
                                n(this._element).one(c.TRANSITION_END, function() {
                                    t.setTransitioning(!1), n(t._element).removeClass(W.COLLAPSING).addClass(W.COLLAPSE).trigger(R.HIDDEN)
                                }).emulateTransitionEnd(u)
                            }
                        }
                    }, e.setTransitioning = function(t) {
                        this._isTransitioning = t
                    }, e.dispose = function() {
                        n.removeData(this._element, "bs.collapse"), this._config = null, this._parent = null, this._element = null, this._triggerArray = null, this._isTransitioning = null
                    }, e._getConfig = function(t) {
                        return (t = s({}, P, t)).toggle = Boolean(t.toggle), c.typeCheckConfig(N, t, H), t
                    }, e._getDimension = function() {
                        var t = n(this._element).hasClass(k.WIDTH);
                        return t ? k.WIDTH : k.HEIGHT
                    }, e._getParent = function() {
                        var e, i = this;
                        c.isElement(this._config.parent) ? (e = this._config.parent, void 0 !== this._config.parent.jquery && (e = this._config.parent[0])) : e = document.querySelector(this._config.parent);
                        var o = '[data-toggle="collapse"][data-parent="' + this._config.parent + '"]',
                            r = [].slice.call(e.querySelectorAll(o));
                        return n(r).each(function(e, n) {
                            i._addAriaAndCollapsedClass(t._getTargetFromElement(n), [n])
                        }), e
                    }, e._addAriaAndCollapsedClass = function(t, e) {
                        var i = n(t).hasClass(W.SHOW);
                        e.length && n(e).toggleClass(W.COLLAPSED, !i).attr("aria-expanded", i)
                    }, t._getTargetFromElement = function(t) {
                        var e = c.getSelectorFromElement(t);
                        return e ? document.querySelector(e) : null
                    }, t._jQueryInterface = function(e) {
                        return this.each(function() {
                            var i = n(this),
                                o = i.data("bs.collapse"),
                                r = s({}, P, i.data(), "object" == typeof e && e ? e : {});
                            if (!o && r.toggle && /show|hide/.test(e) && (r.toggle = !1), o || (o = new t(this, r), i.data("bs.collapse", o)), "string" == typeof e) {
                                if (void 0 === o[e]) throw new TypeError('No method named "' + e + '"');
                                o[e]()
                            }
                        })
                    }, o(t, null, [{
                        key: "VERSION",
                        get: function() {
                            return "4.3.1"
                        }
                    }, {
                        key: "Default",
                        get: function() {
                            return P
                        }
                    }]), t
                }();
            n(document).on(R.CLICK_DATA_API, F.DATA_TOGGLE, function(t) {
                "A" === t.currentTarget.tagName && t.preventDefault();
                var e = n(this),
                    i = c.getSelectorFromElement(this),
                    o = [].slice.call(document.querySelectorAll(i));
                n(o).each(function() {
                    var t = n(this),
                        i = t.data("bs.collapse"),
                        o = i ? "toggle" : e.data();
                    M._jQueryInterface.call(t, o)
                })
            }), n.fn[N] = M._jQueryInterface, n.fn[N].Constructor = M, n.fn[N].noConflict = function() {
                return n.fn[N] = L, M._jQueryInterface
            };
            for (var x = "undefined" != typeof window && "undefined" != typeof document, U = ["Edge", "Trident", "Firefox"], V = 0, j = 0; j < U.length; j += 1)
                if (x && navigator.userAgent.indexOf(U[j]) >= 0) {
                    V = 1;
                    break
                }
            var B = x && window.Promise ? function(t) {
                var e = !1;
                return function() {
                    e || (e = !0, window.Promise.resolve().then(function() {
                        e = !1, t()
                    }))
                }
            } : function(t) {
                var e = !1;
                return function() {
                    e || (e = !0, setTimeout(function() {
                        e = !1, t()
                    }, V))
                }
            };

            function G(t) {
                return t && "[object Function]" === {}.toString.call(t)
            }

            function K(t, e) {
                if (1 !== t.nodeType) return [];
                var n = t.ownerDocument.defaultView,
                    i = n.getComputedStyle(t, null);
                return e ? i[e] : i
            }

            function q(t) {
                return "HTML" === t.nodeName ? t : t.parentNode || t.host
            }

            function Q(t) {
                if (!t) return document.body;
                switch (t.nodeName) {
                    case "HTML":
                    case "BODY":
                        return t.ownerDocument.body;
                    case "#document":
                        return t.body
                }
                var e = K(t),
                    n = e.overflow,
                    i = e.overflowX,
                    o = e.overflowY;
                return /(auto|scroll|overlay)/.test(n + o + i) ? t : Q(q(t))
            }
            var Y = x && !(!window.MSInputMethodContext || !document.documentMode),
                X = x && /MSIE 10/.test(navigator.userAgent);

            function z(t) {
                return 11 === t ? Y : 10 === t ? X : Y || X
            }

            function $(t) {
                if (!t) return document.documentElement;
                for (var e = z(10) ? document.body : null, n = t.offsetParent || null; n === e && t.nextElementSibling;) n = (t = t.nextElementSibling).offsetParent;
                var i = n && n.nodeName;
                return i && "BODY" !== i && "HTML" !== i ? -1 !== ["TH", "TD", "TABLE"].indexOf(n.nodeName) && "static" === K(n, "position") ? $(n) : n : t ? t.ownerDocument.documentElement : document.documentElement
            }

            function J(t) {
                return null !== t.parentNode ? J(t.parentNode) : t
            }

            function Z(t, e) {
                if (!(t && t.nodeType && e && e.nodeType)) return document.documentElement;
                var n = t.compareDocumentPosition(e) & Node.DOCUMENT_POSITION_FOLLOWING,
                    i = n ? t : e,
                    o = n ? e : t,
                    r = document.createRange();
                r.setStart(i, 0), r.setEnd(o, 0);
                var s, a, l = r.commonAncestorContainer;
                if (t !== l && e !== l || i.contains(o)) return "BODY" === (a = (s = l).nodeName) || "HTML" !== a && $(s.firstElementChild) !== s ? $(l) : l;
                var c = J(t);
                return c.host ? Z(c.host, e) : Z(t, J(e).host)
            }

            function tt(t) {
                var e = arguments.length > 1 && void 0 !== arguments[1] ? arguments[1] : "top",
                    n = "top" === e ? "scrollTop" : "scrollLeft",
                    i = t.nodeName;
                if ("BODY" === i || "HTML" === i) {
                    var o = t.ownerDocument.documentElement,
                        r = t.ownerDocument.scrollingElement || o;
                    return r[n]
                }
                return t[n]
            }

            function et(t, e) {
                var n = "x" === e ? "Left" : "Top",
                    i = "Left" === n ? "Right" : "Bottom";
                return parseFloat(t["border" + n + "Width"], 10) + parseFloat(t["border" + i + "Width"], 10)
            }

            function nt(t, e, n, i) {
                return Math.max(e["offset" + t], e["scroll" + t], n["client" + t], n["offset" + t], n["scroll" + t], z(10) ? parseInt(n["offset" + t]) + parseInt(i["margin" + ("Height" === t ? "Top" : "Left")]) + parseInt(i["margin" + ("Height" === t ? "Bottom" : "Right")]) : 0)
            }

            function it(t) {
                var e = t.body,
                    n = t.documentElement,
                    i = z(10) && getComputedStyle(n);
                return {
                    height: nt("Height", e, n, i),
                    width: nt("Width", e, n, i)
                }
            }
            var ot = function(t, e) {
                    if (!(t instanceof e)) throw new TypeError("Cannot call a class as a function")
                },
                rt = function() {
                    function t(t, e) {
                        for (var n = 0; n < e.length; n++) {
                            var i = e[n];
                            i.enumerable = i.enumerable || !1, i.configurable = !0, "value" in i && (i.writable = !0), Object.defineProperty(t, i.key, i)
                        }
                    }
                    return function(e, n, i) {
                        return n && t(e.prototype, n), i && t(e, i), e
                    }
                }(),
                st = function(t, e, n) {
                    return e in t ? Object.defineProperty(t, e, {
                        value: n,
                        enumerable: !0,
                        configurable: !0,
                        writable: !0
                    }) : t[e] = n, t
                },
                at = Object.assign || function(t) {
                    for (var e = arguments, n = 1; n < arguments.length; n++) {
                        var i = e[n];
                        for (var o in i) Object.prototype.hasOwnProperty.call(i, o) && (t[o] = i[o])
                    }
                    return t
                };

            function lt(t) {
                return at({}, t, {
                    right: t.left + t.width,
                    bottom: t.top + t.height
                })
            }

            function ct(t) {
                var e = {};
                try {
                    if (z(10)) {
                        e = t.getBoundingClientRect();
                        var n = tt(t, "top"),
                            i = tt(t, "left");
                        e.top += n, e.left += i, e.bottom += n, e.right += i
                    } else e = t.getBoundingClientRect()
                } catch (t) {}
                var o = {
                        left: e.left,
                        top: e.top,
                        width: e.right - e.left,
                        height: e.bottom - e.top
                    },
                    r = "HTML" === t.nodeName ? it(t.ownerDocument) : {},
                    s = r.width || t.clientWidth || o.right - o.left,
                    a = r.height || t.clientHeight || o.bottom - o.top,
                    l = t.offsetWidth - s,
                    c = t.offsetHeight - a;
                if (l || c) {
                    var u = K(t);
                    l -= et(u, "x"), c -= et(u, "y"), o.width -= l, o.height -= c
                }
                return lt(o)
            }

            function ut(t, e) {
                var n = arguments.length > 2 && void 0 !== arguments[2] && arguments[2],
                    i = z(10),
                    o = "HTML" === e.nodeName,
                    r = ct(t),
                    s = ct(e),
                    a = Q(t),
                    l = K(e),
                    c = parseFloat(l.borderTopWidth, 10),
                    u = parseFloat(l.borderLeftWidth, 10);
                n && o && (s.top = Math.max(s.top, 0), s.left = Math.max(s.left, 0));
                var h = lt({
                    top: r.top - s.top - c,
                    left: r.left - s.left - u,
                    width: r.width,
                    height: r.height
                });
                if (h.marginTop = 0, h.marginLeft = 0, !i && o) {
                    var f = parseFloat(l.marginTop, 10),
                        d = parseFloat(l.marginLeft, 10);
                    h.top -= c - f, h.bottom -= c - f, h.left -= u - d, h.right -= u - d, h.marginTop = f, h.marginLeft = d
                }
                return (i && !n ? e.contains(a) : e === a && "BODY" !== a.nodeName) && (h = function(t, e) {
                    var n = arguments.length > 2 && void 0 !== arguments[2] && arguments[2],
                        i = tt(e, "top"),
                        o = tt(e, "left"),
                        r = n ? -1 : 1;
                    return t.top += i * r, t.bottom += i * r, t.left += o * r, t.right += o * r, t
                }(h, e)), h
            }

            function ht(t) {
                if (!t || !t.parentElement || z()) return document.documentElement;
                for (var e = t.parentElement; e && "none" === K(e, "transform");) e = e.parentElement;
                return e || document.documentElement
            }

            function ft(t, e, n, i) {
                var o = arguments.length > 4 && void 0 !== arguments[4] && arguments[4],
                    r = {
                        top: 0,
                        left: 0
                    },
                    s = o ? ht(t) : Z(t, e);
                if ("viewport" === i) r = function(t) {
                    var e = arguments.length > 1 && void 0 !== arguments[1] && arguments[1],
                        n = t.ownerDocument.documentElement,
                        i = ut(t, n),
                        o = Math.max(n.clientWidth, window.innerWidth || 0),
                        r = Math.max(n.clientHeight, window.innerHeight || 0),
                        s = e ? 0 : tt(n),
                        a = e ? 0 : tt(n, "left");
                    return lt({
                        top: s - i.top + i.marginTop,
                        left: a - i.left + i.marginLeft,
                        width: o,
                        height: r
                    })
                }(s, o);
                else {
                    var a = void 0;
                    "scrollParent" === i ? "BODY" === (a = Q(q(e))).nodeName && (a = t.ownerDocument.documentElement) : a = "window" === i ? t.ownerDocument.documentElement : i;
                    var l = ut(a, s, o);
                    if ("HTML" !== a.nodeName || function t(e) {
                            var n = e.nodeName;
                            if ("BODY" === n || "HTML" === n) return !1;
                            if ("fixed" === K(e, "position")) return !0;
                            var i = q(e);
                            return !!i && t(i)
                        }(s)) r = l;
                    else {
                        var c = it(t.ownerDocument),
                            u = c.height,
                            h = c.width;
                        r.top += l.top - l.marginTop, r.bottom = u + l.top, r.left += l.left - l.marginLeft, r.right = h + l.left
                    }
                }
                var f = "number" == typeof(n = n || 0);
                return r.left += f ? n : n.left || 0, r.top += f ? n : n.top || 0, r.right -= f ? n : n.right || 0, r.bottom -= f ? n : n.bottom || 0, r
            }

            function dt(t, e, n, i, o) {
                var r = arguments.length > 5 && void 0 !== arguments[5] ? arguments[5] : 0;
                if (-1 === t.indexOf("auto")) return t;
                var s = ft(n, i, r, o),
                    a = {
                        top: {
                            width: s.width,
                            height: e.top - s.top
                        },
                        right: {
                            width: s.right - e.right,
                            height: s.height
                        },
                        bottom: {
                            width: s.width,
                            height: s.bottom - e.bottom
                        },
                        left: {
                            width: e.left - s.left,
                            height: s.height
                        }
                    },
                    l = Object.keys(a).map(function(t) {
                        return at({
                            key: t
                        }, a[t], {
                            area: (e = a[t], n = e.width, i = e.height, n * i)
                        });
                        var e, n, i
                    }).sort(function(t, e) {
                        return e.area - t.area
                    }),
                    c = l.filter(function(t) {
                        var e = t.width,
                            i = t.height;
                        return e >= n.clientWidth && i >= n.clientHeight
                    }),
                    u = c.length > 0 ? c[0].key : l[0].key,
                    h = t.split("-")[1];
                return u + (h ? "-" + h : "")
            }

            function pt(t, e, n) {
                var i = arguments.length > 3 && void 0 !== arguments[3] ? arguments[3] : null,
                    o = i ? ht(e) : Z(e, n);
                return ut(n, o, i)
            }

            function mt(t) {
                var e = t.ownerDocument.defaultView,
                    n = e.getComputedStyle(t),
                    i = parseFloat(n.marginTop || 0) + parseFloat(n.marginBottom || 0),
                    o = parseFloat(n.marginLeft || 0) + parseFloat(n.marginRight || 0),
                    r = {
                        width: t.offsetWidth + o,
                        height: t.offsetHeight + i
                    };
                return r
            }

            function gt(t) {
                var e = {
                    left: "right",
                    right: "left",
                    bottom: "top",
                    top: "bottom"
                };
                return t.replace(/left|right|bottom|top/g, function(t) {
                    return e[t]
                })
            }

            function _t(t, e, n) {
                n = n.split("-")[0];
                var i = mt(t),
                    o = {
                        width: i.width,
                        height: i.height
                    },
                    r = -1 !== ["right", "left"].indexOf(n),
                    s = r ? "top" : "left",
                    a = r ? "left" : "top",
                    l = r ? "height" : "width",
                    c = r ? "width" : "height";
                return o[s] = e[s] + e[l] / 2 - i[l] / 2, o[a] = n === a ? e[a] - i[c] : e[gt(a)], o
            }

            function vt(t, e) {
                return Array.prototype.find ? t.find(e) : t.filter(e)[0]
            }

            function Et(t, e, n) {
                var i = void 0 === n ? t : t.slice(0, function(t, e, n) {
                    if (Array.prototype.findIndex) return t.findIndex(function(t) {
                        return t[e] === n
                    });
                    var i = vt(t, function(t) {
                        return t[e] === n
                    });
                    return t.indexOf(i)
                }(t, "name", n));
                return i.forEach(function(t) {
                    t.function && console.warn("`modifier.function` is deprecated, use `modifier.fn`!");
                    var n = t.function || t.fn;
                    t.enabled && G(n) && (e.offsets.popper = lt(e.offsets.popper), e.offsets.reference = lt(e.offsets.reference), e = n(e, t))
                }), e
            }

            function Tt(t, e) {
                return t.some(function(t) {
                    var n = t.name,
                        i = t.enabled;
                    return i && n === e
                })
            }

            function bt(t) {
                for (var e = [!1, "ms", "Webkit", "Moz", "O"], n = t.charAt(0).toUpperCase() + t.slice(1), i = 0; i < e.length; i++) {
                    var o = e[i],
                        r = o ? "" + o + n : t;
                    if (void 0 !== document.body.style[r]) return r
                }
                return null
            }

            function yt(t) {
                var e = t.ownerDocument;
                return e ? e.defaultView : window
            }

            function St(t, e, n, i) {
                n.updateBound = i, yt(t).addEventListener("resize", n.updateBound, {
                    passive: !0
                });
                var o = Q(t);
                return function t(e, n, i, o) {
                    var r = "BODY" === e.nodeName,
                        s = r ? e.ownerDocument.defaultView : e;
                    s.addEventListener(n, i, {
                        passive: !0
                    }), r || t(Q(s.parentNode), n, i, o), o.push(s)
                }(o, "scroll", n.updateBound, n.scrollParents), n.scrollElement = o, n.eventsEnabled = !0, n
            }

            function Ot() {
                var t, e;
                this.state.eventsEnabled && (cancelAnimationFrame(this.scheduleUpdate), this.state = (t = this.reference, e = this.state, yt(t).removeEventListener("resize", e.updateBound), e.scrollParents.forEach(function(t) {
                    t.removeEventListener("scroll", e.updateBound)
                }), e.updateBound = null, e.scrollParents = [], e.scrollElement = null, e.eventsEnabled = !1, e))
            }

            function It(t) {
                return "" !== t && !isNaN(parseFloat(t)) && isFinite(t)
            }

            function Ct(t, e) {
                Object.keys(e).forEach(function(n) {
                    var i = ""; - 1 !== ["width", "height", "top", "right", "bottom", "left"].indexOf(n) && It(e[n]) && (i = "px"), t.style[n] = e[n] + i
                })
            }
            var At = x && /Firefox/i.test(navigator.userAgent);

            function Dt(t, e, n) {
                var i = vt(t, function(t) {
                        var n = t.name;
                        return n === e
                    }),
                    o = !!i && t.some(function(t) {
                        return t.name === n && t.enabled && t.order < i.order
                    });
                if (!o) {
                    var r = "`" + e + "`",
                        s = "`" + n + "`";
                    console.warn(s + " modifier is required by " + r + " modifier in order to work, be sure to include it before " + r + "!")
                }
                return o
            }
            var wt = ["auto-start", "auto", "auto-end", "top-start", "top", "top-end", "right-start", "right", "right-end", "bottom-end", "bottom", "bottom-start", "left-end", "left", "left-start"],
                Nt = wt.slice(3);

            function Lt(t) {
                var e = arguments.length > 1 && void 0 !== arguments[1] && arguments[1],
                    n = Nt.indexOf(t),
                    i = Nt.slice(n + 1).concat(Nt.slice(0, n));
                return e ? i.reverse() : i
            }
            var Pt = {
                FLIP: "flip",
                CLOCKWISE: "clockwise",
                COUNTERCLOCKWISE: "counterclockwise"
            };

            function Ht(t, e, n, i) {
                var o = [0, 0],
                    r = -1 !== ["right", "left"].indexOf(i),
                    s = t.split(/(\+|\-)/).map(function(t) {
                        return t.trim()
                    }),
                    a = s.indexOf(vt(s, function(t) {
                        return -1 !== t.search(/,|\s/)
                    }));
                s[a] && -1 === s[a].indexOf(",") && console.warn("Offsets separated by white space(s) are deprecated, use a comma (,) instead.");
                var l = /\s*,\s*|\s+/,
                    c = -1 !== a ? [s.slice(0, a).concat([s[a].split(l)[0]]), [s[a].split(l)[1]].concat(s.slice(a + 1))] : [s];
                return (c = c.map(function(t, i) {
                    var o = (1 === i ? !r : r) ? "height" : "width",
                        s = !1;
                    return t.reduce(function(t, e) {
                        return "" === t[t.length - 1] && -1 !== ["+", "-"].indexOf(e) ? (t[t.length - 1] = e, s = !0, t) : s ? (t[t.length - 1] += e, s = !1, t) : t.concat(e)
                    }, []).map(function(t) {
                        return function(t, e, n, i) {
                            var o = t.match(/((?:\-|\+)?\d*\.?\d*)(.*)/),
                                r = +o[1],
                                s = o[2];
                            if (!r) return t;
                            if (0 === s.indexOf("%")) {
                                var a = void 0;
                                switch (s) {
                                    case "%p":
                                        a = n;
                                        break;
                                    case "%":
                                    case "%r":
                                    default:
                                        a = i
                                }
                                var l = lt(a);
                                return l[e] / 100 * r
                            }
                            return "vh" === s || "vw" === s ? ("vh" === s ? Math.max(document.documentElement.clientHeight, window.innerHeight || 0) : Math.max(document.documentElement.clientWidth, window.innerWidth || 0)) / 100 * r : r
                        }(t, o, e, n)
                    })
                })).forEach(function(t, e) {
                    t.forEach(function(n, i) {
                        It(n) && (o[e] += n * ("-" === t[i - 1] ? -1 : 1))
                    })
                }), o
            }
            var Rt = {
                    placement: "bottom",
                    positionFixed: !1,
                    eventsEnabled: !0,
                    removeOnDestroy: !1,
                    onCreate: function() {},
                    onUpdate: function() {},
                    modifiers: {
                        shift: {
                            order: 100,
                            enabled: !0,
                            fn: function(t) {
                                var e = t.placement,
                                    n = e.split("-")[0],
                                    i = e.split("-")[1];
                                if (i) {
                                    var o = t.offsets,
                                        r = o.reference,
                                        s = o.popper,
                                        a = -1 !== ["bottom", "top"].indexOf(n),
                                        l = a ? "left" : "top",
                                        c = a ? "width" : "height",
                                        u = {
                                            start: st({}, l, r[l]),
                                            end: st({}, l, r[l] + r[c] - s[c])
                                        };
                                    t.offsets.popper = at({}, s, u[i])
                                }
                                return t
                            }
                        },
                        offset: {
                            order: 200,
                            enabled: !0,
                            fn: function(t, e) {
                                var n = e.offset,
                                    i = t.placement,
                                    o = t.offsets,
                                    r = o.popper,
                                    s = o.reference,
                                    a = i.split("-")[0],
                                    l = void 0;
                                return l = It(+n) ? [+n, 0] : Ht(n, r, s, a), "left" === a ? (r.top += l[0], r.left -= l[1]) : "right" === a ? (r.top += l[0], r.left += l[1]) : "top" === a ? (r.left += l[0], r.top -= l[1]) : "bottom" === a && (r.left += l[0], r.top += l[1]), t.popper = r, t
                            },
                            offset: 0
                        },
                        preventOverflow: {
                            order: 300,
                            enabled: !0,
                            fn: function(t, e) {
                                var n = e.boundariesElement || $(t.instance.popper);
                                t.instance.reference === n && (n = $(n));
                                var i = bt("transform"),
                                    o = t.instance.popper.style,
                                    r = o.top,
                                    s = o.left,
                                    a = o[i];
                                o.top = "", o.left = "", o[i] = "";
                                var l = ft(t.instance.popper, t.instance.reference, e.padding, n, t.positionFixed);
                                o.top = r, o.left = s, o[i] = a, e.boundaries = l;
                                var c = e.priority,
                                    u = t.offsets.popper,
                                    h = {
                                        primary: function(t) {
                                            var n = u[t];
                                            return u[t] < l[t] && !e.escapeWithReference && (n = Math.max(u[t], l[t])), st({}, t, n)
                                        },
                                        secondary: function(t) {
                                            var n = "right" === t ? "left" : "top",
                                                i = u[n];
                                            return u[t] > l[t] && !e.escapeWithReference && (i = Math.min(u[n], l[t] - ("right" === t ? u.width : u.height))), st({}, n, i)
                                        }
                                    };
                                return c.forEach(function(t) {
                                    var e = -1 !== ["left", "top"].indexOf(t) ? "primary" : "secondary";
                                    u = at({}, u, h[e](t))
                                }), t.offsets.popper = u, t
                            },
                            priority: ["left", "right", "top", "bottom"],
                            padding: 5,
                            boundariesElement: "scrollParent"
                        },
                        keepTogether: {
                            order: 400,
                            enabled: !0,
                            fn: function(t) {
                                var e = t.offsets,
                                    n = e.popper,
                                    i = e.reference,
                                    o = t.placement.split("-")[0],
                                    r = Math.floor,
                                    s = -1 !== ["top", "bottom"].indexOf(o),
                                    a = s ? "right" : "bottom",
                                    l = s ? "left" : "top",
                                    c = s ? "width" : "height";
                                return n[a] < r(i[l]) && (t.offsets.popper[l] = r(i[l]) - n[c]), n[l] > r(i[a]) && (t.offsets.popper[l] = r(i[a])), t
                            }
                        },
                        arrow: {
                            order: 500,
                            enabled: !0,
                            fn: function(t, e) {
                                var n;
                                if (!Dt(t.instance.modifiers, "arrow", "keepTogether")) return t;
                                var i = e.element;
                                if ("string" == typeof i) {
                                    if (!(i = t.instance.popper.querySelector(i))) return t
                                } else if (!t.instance.popper.contains(i)) return console.warn("WARNING: `arrow.element` must be child of its popper element!"), t;
                                var o = t.placement.split("-")[0],
                                    r = t.offsets,
                                    s = r.popper,
                                    a = r.reference,
                                    l = -1 !== ["left", "right"].indexOf(o),
                                    c = l ? "height" : "width",
                                    u = l ? "Top" : "Left",
                                    h = u.toLowerCase(),
                                    f = l ? "left" : "top",
                                    d = l ? "bottom" : "right",
                                    p = mt(i)[c];
                                a[d] - p < s[h] && (t.offsets.popper[h] -= s[h] - (a[d] - p)), a[h] + p > s[d] && (t.offsets.popper[h] += a[h] + p - s[d]), t.offsets.popper = lt(t.offsets.popper);
                                var m = a[h] + a[c] / 2 - p / 2,
                                    g = K(t.instance.popper),
                                    _ = parseFloat(g["margin" + u], 10),
                                    v = parseFloat(g["border" + u + "Width"], 10),
                                    E = m - t.offsets.popper[h] - _ - v;
                                return E = Math.max(Math.min(s[c] - p, E), 0), t.arrowElement = i, t.offsets.arrow = (st(n = {}, h, Math.round(E)), st(n, f, ""), n), t
                            },
                            element: "[x-arrow]"
                        },
                        flip: {
                            order: 600,
                            enabled: !0,
                            fn: function(t, e) {
                                if (Tt(t.instance.modifiers, "inner")) return t;
                                if (t.flipped && t.placement === t.originalPlacement) return t;
                                var n = ft(t.instance.popper, t.instance.reference, e.padding, e.boundariesElement, t.positionFixed),
                                    i = t.placement.split("-")[0],
                                    o = gt(i),
                                    r = t.placement.split("-")[1] || "",
                                    s = [];
                                switch (e.behavior) {
                                    case Pt.FLIP:
                                        s = [i, o];
                                        break;
                                    case Pt.CLOCKWISE:
                                        s = Lt(i);
                                        break;
                                    case Pt.COUNTERCLOCKWISE:
                                        s = Lt(i, !0);
                                        break;
                                    default:
                                        s = e.behavior
                                }
                                return s.forEach(function(a, l) {
                                    if (i !== a || s.length === l + 1) return t;
                                    i = t.placement.split("-")[0], o = gt(i);
                                    var c = t.offsets.popper,
                                        u = t.offsets.reference,
                                        h = Math.floor,
                                        f = "left" === i && h(c.right) > h(u.left) || "right" === i && h(c.left) < h(u.right) || "top" === i && h(c.bottom) > h(u.top) || "bottom" === i && h(c.top) < h(u.bottom),
                                        d = h(c.left) < h(n.left),
                                        p = h(c.right) > h(n.right),
                                        m = h(c.top) < h(n.top),
                                        g = h(c.bottom) > h(n.bottom),
                                        _ = "left" === i && d || "right" === i && p || "top" === i && m || "bottom" === i && g,
                                        v = -1 !== ["top", "bottom"].indexOf(i),
                                        E = !!e.flipVariations && (v && "start" === r && d || v && "end" === r && p || !v && "start" === r && m || !v && "end" === r && g);
                                    (f || _ || E) && (t.flipped = !0, (f || _) && (i = s[l + 1]), E && (r = function(t) {
                                        return "end" === t ? "start" : "start" === t ? "end" : t
                                    }(r)), t.placement = i + (r ? "-" + r : ""), t.offsets.popper = at({}, t.offsets.popper, _t(t.instance.popper, t.offsets.reference, t.placement)), t = Et(t.instance.modifiers, t, "flip"))
                                }), t
                            },
                            behavior: "flip",
                            padding: 5,
                            boundariesElement: "viewport"
                        },
                        inner: {
                            order: 700,
                            enabled: !1,
                            fn: function(t) {
                                var e = t.placement,
                                    n = e.split("-")[0],
                                    i = t.offsets,
                                    o = i.popper,
                                    r = i.reference,
                                    s = -1 !== ["left", "right"].indexOf(n),
                                    a = -1 === ["top", "left"].indexOf(n);
                                return o[s ? "left" : "top"] = r[n] - (a ? o[s ? "width" : "height"] : 0), t.placement = gt(e), t.offsets.popper = lt(o), t
                            }
                        },
                        hide: {
                            order: 800,
                            enabled: !0,
                            fn: function(t) {
                                if (!Dt(t.instance.modifiers, "hide", "preventOverflow")) return t;
                                var e = t.offsets.reference,
                                    n = vt(t.instance.modifiers, function(t) {
                                        return "preventOverflow" === t.name
                                    }).boundaries;
                                if (e.bottom < n.top || e.left > n.right || e.top > n.bottom || e.right < n.left) {
                                    if (!0 === t.hide) return t;
                                    t.hide = !0, t.attributes["x-out-of-boundaries"] = ""
                                } else {
                                    if (!1 === t.hide) return t;
                                    t.hide = !1, t.attributes["x-out-of-boundaries"] = !1
                                }
                                return t
                            }
                        },
                        computeStyle: {
                            order: 850,
                            enabled: !0,
                            fn: function(t, e) {
                                var n = e.x,
                                    i = e.y,
                                    o = t.offsets.popper,
                                    r = vt(t.instance.modifiers, function(t) {
                                        return "applyStyle" === t.name
                                    }).gpuAcceleration;
                                void 0 !== r && console.warn("WARNING: `gpuAcceleration` option moved to `computeStyle` modifier and will not be supported in future versions of Popper.js!");
                                var s = void 0 !== r ? r : e.gpuAcceleration,
                                    a = $(t.instance.popper),
                                    l = ct(a),
                                    c = {
                                        position: o.position
                                    },
                                    u = function(t, e) {
                                        var n = t.offsets,
                                            i = n.popper,
                                            o = n.reference,
                                            r = Math.round,
                                            s = Math.floor,
                                            a = function(t) {
                                                return t
                                            },
                                            l = r(o.width),
                                            c = r(i.width),
                                            u = -1 !== ["left", "right"].indexOf(t.placement),
                                            h = -1 !== t.placement.indexOf("-"),
                                            f = l % 2 == c % 2,
                                            d = e ? u || h || f ? r : s : a,
                                            p = e ? r : a;
                                        return {
                                            left: d(l % 2 == 1 && c % 2 == 1 && !h && e ? i.left - 1 : i.left),
                                            top: p(i.top),
                                            bottom: p(i.bottom),
                                            right: d(i.right)
                                        }
                                    }(t, window.devicePixelRatio < 2 || !At),
                                    h = "bottom" === n ? "top" : "bottom",
                                    f = "right" === i ? "left" : "right",
                                    d = bt("transform"),
                                    p = void 0,
                                    m = void 0;
                                if (m = "bottom" === h ? "HTML" === a.nodeName ? -a.clientHeight + u.bottom : -l.height + u.bottom : u.top, p = "right" === f ? "HTML" === a.nodeName ? -a.clientWidth + u.right : -l.width + u.right : u.left, s && d) c[d] = "translate3d(" + p + "px, " + m + "px, 0)", c[h] = 0, c[f] = 0, c.willChange = "transform";
                                else {
                                    var g = "bottom" === h ? -1 : 1,
                                        _ = "right" === f ? -1 : 1;
                                    c[h] = m * g, c[f] = p * _, c.willChange = h + ", " + f
                                }
                                var v = {
                                    "x-placement": t.placement
                                };
                                return t.attributes = at({}, v, t.attributes), t.styles = at({}, c, t.styles), t.arrowStyles = at({}, t.offsets.arrow, t.arrowStyles), t
                            },
                            gpuAcceleration: !0,
                            x: "bottom",
                            y: "right"
                        },
                        applyStyle: {
                            order: 900,
                            enabled: !0,
                            fn: function(t) {
                                var e, n;
                                return Ct(t.instance.popper, t.styles), e = t.instance.popper, n = t.attributes, Object.keys(n).forEach(function(t) {
                                    var i = n[t];
                                    !1 !== i ? e.setAttribute(t, n[t]) : e.removeAttribute(t)
                                }), t.arrowElement && Object.keys(t.arrowStyles).length && Ct(t.arrowElement, t.arrowStyles), t
                            },
                            onLoad: function(t, e, n, i, o) {
                                var r = pt(o, e, t, n.positionFixed),
                                    s = dt(n.placement, r, e, t, n.modifiers.flip.boundariesElement, n.modifiers.flip.padding);
                                return e.setAttribute("x-placement", s), Ct(e, {
                                    position: n.positionFixed ? "fixed" : "absolute"
                                }), n
                            },
                            gpuAcceleration: void 0
                        }
                    }
                },
                Wt = function() {
                    function t(e, n) {
                        var i = this,
                            o = arguments.length > 2 && void 0 !== arguments[2] ? arguments[2] : {};
                        ot(this, t), this.scheduleUpdate = function() {
                            return requestAnimationFrame(i.update)
                        }, this.update = B(this.update.bind(this)), this.options = at({}, t.Defaults, o), this.state = {
                            isDestroyed: !1,
                            isCreated: !1,
                            scrollParents: []
                        }, this.reference = e && e.jquery ? e[0] : e, this.popper = n && n.jquery ? n[0] : n, this.options.modifiers = {}, Object.keys(at({}, t.Defaults.modifiers, o.modifiers)).forEach(function(e) {
                            i.options.modifiers[e] = at({}, t.Defaults.modifiers[e] || {}, o.modifiers ? o.modifiers[e] : {})
                        }), this.modifiers = Object.keys(this.options.modifiers).map(function(t) {
                            return at({
                                name: t
                            }, i.options.modifiers[t])
                        }).sort(function(t, e) {
                            return t.order - e.order
                        }), this.modifiers.forEach(function(t) {
                            t.enabled && G(t.onLoad) && t.onLoad(i.reference, i.popper, i.options, t, i.state)
                        }), this.update();
                        var r = this.options.eventsEnabled;
                        r && this.enableEventListeners(), this.state.eventsEnabled = r
                    }
                    return rt(t, [{
                        key: "update",
                        value: function() {
                            return function() {
                                if (!this.state.isDestroyed) {
                                    var t = {
                                        instance: this,
                                        styles: {},
                                        arrowStyles: {},
                                        attributes: {},
                                        flipped: !1,
                                        offsets: {}
                                    };
                                    t.offsets.reference = pt(this.state, this.popper, this.reference, this.options.positionFixed), t.placement = dt(this.options.placement, t.offsets.reference, this.popper, this.reference, this.options.modifiers.flip.boundariesElement, this.options.modifiers.flip.padding), t.originalPlacement = t.placement, t.positionFixed = this.options.positionFixed, t.offsets.popper = _t(this.popper, t.offsets.reference, t.placement), t.offsets.popper.position = this.options.positionFixed ? "fixed" : "absolute", t = Et(this.modifiers, t), this.state.isCreated ? this.options.onUpdate(t) : (this.state.isCreated = !0, this.options.onCreate(t))
                                }
                            }.call(this)
                        }
                    }, {
                        key: "destroy",
                        value: function() {
                            return function() {
                                return this.state.isDestroyed = !0, Tt(this.modifiers, "applyStyle") && (this.popper.removeAttribute("x-placement"), this.popper.style.position = "", this.popper.style.top = "", this.popper.style.left = "", this.popper.style.right = "", this.popper.style.bottom = "", this.popper.style.willChange = "", this.popper.style[bt("transform")] = ""), this.disableEventListeners(), this.options.removeOnDestroy && this.popper.parentNode.removeChild(this.popper), this
                            }.call(this)
                        }
                    }, {
                        key: "enableEventListeners",
                        value: function() {
                            return function() {
                                this.state.eventsEnabled || (this.state = St(this.reference, this.options, this.state, this.scheduleUpdate))
                            }.call(this)
                        }
                    }, {
                        key: "disableEventListeners",
                        value: function() {
                            return Ot.call(this)
                        }
                    }]), t
                }();
            Wt.Utils = ("undefined" != typeof window ? window : e).PopperUtils, Wt.placements = wt, Wt.Defaults = Rt;
            var kt = "dropdown",
                Ft = n.fn[kt],
                Mt = new RegExp("38|40|27"),
                xt = {
                    HIDE: "hide.bs.dropdown",
                    HIDDEN: "hidden.bs.dropdown",
                    SHOW: "show.bs.dropdown",
                    SHOWN: "shown.bs.dropdown",
                    CLICK: "click.bs.dropdown",
                    CLICK_DATA_API: "click.bs.dropdown.data-api",
                    KEYDOWN_DATA_API: "keydown.bs.dropdown.data-api",
                    KEYUP_DATA_API: "keyup.bs.dropdown.data-api"
                },
                Ut = {
                    DISABLED: "disabled",
                    SHOW: "show",
                    DROPUP: "dropup",
                    DROPRIGHT: "dropright",
                    DROPLEFT: "dropleft",
                    MENURIGHT: "dropdown-menu-right",
                    MENULEFT: "dropdown-menu-left",
                    POSITION_STATIC: "position-static"
                },
                Vt = {
                    DATA_TOGGLE: '[data-toggle="dropdown"]',
                    FORM_CHILD: ".dropdown form",
                    MENU: ".dropdown-menu",
                    NAVBAR_NAV: ".navbar-nav",
                    VISIBLE_ITEMS: ".dropdown-menu .dropdown-item:not(.disabled):not(:disabled)"
                },
                jt = {
                    TOP: "top-start",
                    TOPEND: "top-end",
                    BOTTOM: "bottom-start",
                    BOTTOMEND: "bottom-end",
                    RIGHT: "right-start",
                    RIGHTEND: "right-end",
                    LEFT: "left-start",
                    LEFTEND: "left-end"
                },
                Bt = {
                    offset: 0,
                    flip: !0,
                    boundary: "scrollParent",
                    reference: "toggle",
                    display: "dynamic"
                },
                Gt = {
                    offset: "(number|string|function)",
                    flip: "boolean",
                    boundary: "(string|element)",
                    reference: "(string|element)",
                    display: "string"
                },
                Kt = function() {
                    function t(t, e) {
                        this._element = t, this._popper = null, this._config = this._getConfig(e), this._menu = this._getMenuElement(), this._inNavbar = this._detectNavbar(), this._addEventListeners()
                    }
                    var e = t.prototype;
                    return e.toggle = function() {
                        if (!this._element.disabled && !n(this._element).hasClass(Ut.DISABLED)) {
                            var e = t._getParentFromElement(this._element),
                                i = n(this._menu).hasClass(Ut.SHOW);
                            if (t._clearMenus(), !i) {
                                var o = {
                                        relatedTarget: this._element
                                    },
                                    r = n.Event(xt.SHOW, o);
                                if (n(e).trigger(r), !r.isDefaultPrevented()) {
                                    if (!this._inNavbar) {
                                        if (void 0 === Wt) throw new TypeError("Bootstrap's dropdowns require Popper.js (https://popper.js.org/)");
                                        var s = this._element;
                                        "parent" === this._config.reference ? s = e : c.isElement(this._config.reference) && (s = this._config.reference, void 0 !== this._config.reference.jquery && (s = this._config.reference[0])), "scrollParent" !== this._config.boundary && n(e).addClass(Ut.POSITION_STATIC), this._popper = new Wt(s, this._menu, this._getPopperConfig())
                                    }
                                    "ontouchstart" in document.documentElement && 0 === n(e).closest(Vt.NAVBAR_NAV).length && n(document.body).children().on("mouseover", null, n.noop), this._element.focus(), this._element.setAttribute("aria-expanded", !0), n(this._menu).toggleClass(Ut.SHOW), n(e).toggleClass(Ut.SHOW).trigger(n.Event(xt.SHOWN, o))
                                }
                            }
                        }
                    }, e.show = function() {
                        if (!(this._element.disabled || n(this._element).hasClass(Ut.DISABLED) || n(this._menu).hasClass(Ut.SHOW))) {
                            var e = {
                                    relatedTarget: this._element
                                },
                                i = n.Event(xt.SHOW, e),
                                o = t._getParentFromElement(this._element);
                            n(o).trigger(i), i.isDefaultPrevented() || (n(this._menu).toggleClass(Ut.SHOW), n(o).toggleClass(Ut.SHOW).trigger(n.Event(xt.SHOWN, e)))
                        }
                    }, e.hide = function() {
                        if (!this._element.disabled && !n(this._element).hasClass(Ut.DISABLED) && n(this._menu).hasClass(Ut.SHOW)) {
                            var e = {
                                    relatedTarget: this._element
                                },
                                i = n.Event(xt.HIDE, e),
                                o = t._getParentFromElement(this._element);
                            n(o).trigger(i), i.isDefaultPrevented() || (n(this._menu).toggleClass(Ut.SHOW), n(o).toggleClass(Ut.SHOW).trigger(n.Event(xt.HIDDEN, e)))
                        }
                    }, e.dispose = function() {
                        n.removeData(this._element, "bs.dropdown"), n(this._element).off(".bs.dropdown"), this._element = null, this._menu = null, null !== this._popper && (this._popper.destroy(), this._popper = null)
                    }, e.update = function() {
                        this._inNavbar = this._detectNavbar(), null !== this._popper && this._popper.scheduleUpdate()
                    }, e._addEventListeners = function() {
                        var t = this;
                        n(this._element).on(xt.CLICK, function(e) {
                            e.preventDefault(), e.stopPropagation(), t.toggle()
                        })
                    }, e._getConfig = function(t) {
                        return t = s({}, this.constructor.Default, n(this._element).data(), t), c.typeCheckConfig(kt, t, this.constructor.DefaultType), t
                    }, e._getMenuElement = function() {
                        if (!this._menu) {
                            var e = t._getParentFromElement(this._element);
                            e && (this._menu = e.querySelector(Vt.MENU))
                        }
                        return this._menu
                    }, e._getPlacement = function() {
                        var t = n(this._element.parentNode),
                            e = jt.BOTTOM;
                        return t.hasClass(Ut.DROPUP) ? (e = jt.TOP, n(this._menu).hasClass(Ut.MENURIGHT) && (e = jt.TOPEND)) : t.hasClass(Ut.DROPRIGHT) ? e = jt.RIGHT : t.hasClass(Ut.DROPLEFT) ? e = jt.LEFT : n(this._menu).hasClass(Ut.MENURIGHT) && (e = jt.BOTTOMEND), e
                    }, e._detectNavbar = function() {
                        return n(this._element).closest(".navbar").length > 0
                    }, e._getOffset = function() {
                        var t = this,
                            e = {};
                        return "function" == typeof this._config.offset ? e.fn = function(e) {
                            return e.offsets = s({}, e.offsets, t._config.offset(e.offsets, t._element) || {}), e
                        } : e.offset = this._config.offset, e
                    }, e._getPopperConfig = function() {
                        var t = {
                            placement: this._getPlacement(),
                            modifiers: {
                                offset: this._getOffset(),
                                flip: {
                                    enabled: this._config.flip
                                },
                                preventOverflow: {
                                    boundariesElement: this._config.boundary
                                }
                            }
                        };
                        return "static" === this._config.display && (t.modifiers.applyStyle = {
                            enabled: !1
                        }), t
                    }, t._jQueryInterface = function(e) {
                        return this.each(function() {
                            var i = n(this).data("bs.dropdown"),
                                o = "object" == typeof e ? e : null;
                            if (i || (i = new t(this, o), n(this).data("bs.dropdown", i)), "string" == typeof e) {
                                if (void 0 === i[e]) throw new TypeError('No method named "' + e + '"');
                                i[e]()
                            }
                        })
                    }, t._clearMenus = function(e) {
                        if (!e || 3 !== e.which && ("keyup" !== e.type || 9 === e.which))
                            for (var i = [].slice.call(document.querySelectorAll(Vt.DATA_TOGGLE)), o = 0, r = i.length; o < r; o++) {
                                var s = t._getParentFromElement(i[o]),
                                    a = n(i[o]).data("bs.dropdown"),
                                    l = {
                                        relatedTarget: i[o]
                                    };
                                if (e && "click" === e.type && (l.clickEvent = e), a) {
                                    var c = a._menu;
                                    if (n(s).hasClass(Ut.SHOW) && !(e && ("click" === e.type && /input|textarea/i.test(e.target.tagName) || "keyup" === e.type && 9 === e.which) && n.contains(s, e.target))) {
                                        var u = n.Event(xt.HIDE, l);
                                        n(s).trigger(u), u.isDefaultPrevented() || ("ontouchstart" in document.documentElement && n(document.body).children().off("mouseover", null, n.noop), i[o].setAttribute("aria-expanded", "false"), n(c).removeClass(Ut.SHOW), n(s).removeClass(Ut.SHOW).trigger(n.Event(xt.HIDDEN, l)))
                                    }
                                }
                            }
                    }, t._getParentFromElement = function(t) {
                        var e, n = c.getSelectorFromElement(t);
                        return n && (e = document.querySelector(n)), e || t.parentNode
                    }, t._dataApiKeydownHandler = function(e) {
                        if ((/input|textarea/i.test(e.target.tagName) ? !(32 === e.which || 27 !== e.which && (40 !== e.which && 38 !== e.which || n(e.target).closest(Vt.MENU).length)) : Mt.test(e.which)) && (e.preventDefault(), e.stopPropagation(), !this.disabled && !n(this).hasClass(Ut.DISABLED))) {
                            var i = t._getParentFromElement(this),
                                o = n(i).hasClass(Ut.SHOW);
                            if (o && (!o || 27 !== e.which && 32 !== e.which)) {
                                var r = [].slice.call(i.querySelectorAll(Vt.VISIBLE_ITEMS));
                                if (0 !== r.length) {
                                    var s = r.indexOf(e.target);
                                    38 === e.which && s > 0 && s--, 40 === e.which && s < r.length - 1 && s++, s < 0 && (s = 0), r[s].focus()
                                }
                            } else {
                                if (27 === e.which) {
                                    var a = i.querySelector(Vt.DATA_TOGGLE);
                                    n(a).trigger("focus")
                                }
                                n(this).trigger("click")
                            }
                        }
                    }, o(t, null, [{
                        key: "VERSION",
                        get: function() {
                            return "4.3.1"
                        }
                    }, {
                        key: "Default",
                        get: function() {
                            return Bt
                        }
                    }, {
                        key: "DefaultType",
                        get: function() {
                            return Gt
                        }
                    }]), t
                }();
            n(document).on(xt.KEYDOWN_DATA_API, Vt.DATA_TOGGLE, Kt._dataApiKeydownHandler).on(xt.KEYDOWN_DATA_API, Vt.MENU, Kt._dataApiKeydownHandler).on(xt.CLICK_DATA_API + " " + xt.KEYUP_DATA_API, Kt._clearMenus).on(xt.CLICK_DATA_API, Vt.DATA_TOGGLE, function(t) {
                t.preventDefault(), t.stopPropagation(), Kt._jQueryInterface.call(n(this), "toggle")
            }).on(xt.CLICK_DATA_API, Vt.FORM_CHILD, function(t) {
                t.stopPropagation()
            }), n.fn[kt] = Kt._jQueryInterface, n.fn[kt].Constructor = Kt, n.fn[kt].noConflict = function() {
                return n.fn[kt] = Ft, Kt._jQueryInterface
            };
            var qt = n.fn.modal,
                Qt = {
                    backdrop: !0,
                    keyboard: !0,
                    focus: !0,
                    show: !0
                },
                Yt = {
                    backdrop: "(boolean|string)",
                    keyboard: "boolean",
                    focus: "boolean",
                    show: "boolean"
                },
                Xt = {
                    HIDE: "hide.bs.modal",
                    HIDDEN: "hidden.bs.modal",
                    SHOW: "show.bs.modal",
                    SHOWN: "shown.bs.modal",
                    FOCUSIN: "focusin.bs.modal",
                    RESIZE: "resize.bs.modal",
                    CLICK_DISMISS: "click.dismiss.bs.modal",
                    KEYDOWN_DISMISS: "keydown.dismiss.bs.modal",
                    MOUSEUP_DISMISS: "mouseup.dismiss.bs.modal",
                    MOUSEDOWN_DISMISS: "mousedown.dismiss.bs.modal",
                    CLICK_DATA_API: "click.bs.modal.data-api"
                },
                zt = {
                    SCROLLABLE: "modal-dialog-scrollable",
                    SCROLLBAR_MEASURER: "modal-scrollbar-measure",
                    BACKDROP: "modal-backdrop",
                    OPEN: "modal-open",
                    FADE: "fade",
                    SHOW: "show"
                },
                $t = {
                    DIALOG: ".modal-dialog",
                    MODAL_BODY: ".modal-body",
                    DATA_TOGGLE: '[data-toggle="modal"]',
                    DATA_DISMISS: '[data-dismiss="modal"]',
                    FIXED_CONTENT: ".fixed-top, .fixed-bottom, .is-fixed, .sticky-top",
                    STICKY_CONTENT: ".sticky-top"
                },
                Jt = function() {
                    function t(t, e) {
                        this._config = this._getConfig(e), this._element = t, this._dialog = t.querySelector($t.DIALOG), this._backdrop = null, this._isShown = !1, this._isBodyOverflowing = !1, this._ignoreBackdropClick = !1, this._isTransitioning = !1, this._scrollbarWidth = 0
                    }
                    var e = t.prototype;
                    return e.toggle = function(t) {
                        return this._isShown ? this.hide() : this.show(t)
                    }, e.show = function(t) {
                        var e = this;
                        if (!this._isShown && !this._isTransitioning) {
                            n(this._element).hasClass(zt.FADE) && (this._isTransitioning = !0);
                            var i = n.Event(Xt.SHOW, {
                                relatedTarget: t
                            });
                            n(this._element).trigger(i), this._isShown || i.isDefaultPrevented() || (this._isShown = !0, this._checkScrollbar(), this._setScrollbar(), this._adjustDialog(), this._setEscapeEvent(), this._setResizeEvent(), n(this._element).on(Xt.CLICK_DISMISS, $t.DATA_DISMISS, function(t) {
                                return e.hide(t)
                            }), n(this._dialog).on(Xt.MOUSEDOWN_DISMISS, function() {
                                n(e._element).one(Xt.MOUSEUP_DISMISS, function(t) {
                                    n(t.target).is(e._element) && (e._ignoreBackdropClick = !0)
                                })
                            }), this._showBackdrop(function() {
                                return e._showElement(t)
                            }))
                        }
                    }, e.hide = function(t) {
                        var e = this;
                        if (t && t.preventDefault(), this._isShown && !this._isTransitioning) {
                            var i = n.Event(Xt.HIDE);
                            if (n(this._element).trigger(i), this._isShown && !i.isDefaultPrevented()) {
                                this._isShown = !1;
                                var o = n(this._element).hasClass(zt.FADE);
                                if (o && (this._isTransitioning = !0), this._setEscapeEvent(), this._setResizeEvent(), n(document).off(Xt.FOCUSIN), n(this._element).removeClass(zt.SHOW), n(this._element).off(Xt.CLICK_DISMISS), n(this._dialog).off(Xt.MOUSEDOWN_DISMISS), o) {
                                    var r = c.getTransitionDurationFromElement(this._element);
                                    n(this._element).one(c.TRANSITION_END, function(t) {
                                        return e._hideModal(t)
                                    }).emulateTransitionEnd(r)
                                } else this._hideModal()
                            }
                        }
                    }, e.dispose = function() {
                        [window, this._element, this._dialog].forEach(function(t) {
                            return n(t).off(".bs.modal")
                        }), n(document).off(Xt.FOCUSIN), n.removeData(this._element, "bs.modal"), this._config = null, this._element = null, this._dialog = null, this._backdrop = null, this._isShown = null, this._isBodyOverflowing = null, this._ignoreBackdropClick = null, this._isTransitioning = null, this._scrollbarWidth = null
                    }, e.handleUpdate = function() {
                        this._adjustDialog()
                    }, e._getConfig = function(t) {
                        return t = s({}, Qt, t), c.typeCheckConfig("modal", t, Yt), t
                    }, e._showElement = function(t) {
                        var e = this,
                            i = n(this._element).hasClass(zt.FADE);
                        this._element.parentNode && this._element.parentNode.nodeType === Node.ELEMENT_NODE || document.body.appendChild(this._element), this._element.style.display = "block", this._element.removeAttribute("aria-hidden"), this._element.setAttribute("aria-modal", !0), n(this._dialog).hasClass(zt.SCROLLABLE) ? this._dialog.querySelector($t.MODAL_BODY).scrollTop = 0 : this._element.scrollTop = 0, i && c.reflow(this._element), n(this._element).addClass(zt.SHOW), this._config.focus && this._enforceFocus();
                        var o = n.Event(Xt.SHOWN, {
                                relatedTarget: t
                            }),
                            r = function() {
                                e._config.focus && e._element.focus(), e._isTransitioning = !1, n(e._element).trigger(o)
                            };
                        if (i) {
                            var s = c.getTransitionDurationFromElement(this._dialog);
                            n(this._dialog).one(c.TRANSITION_END, r).emulateTransitionEnd(s)
                        } else r()
                    }, e._enforceFocus = function() {
                        var t = this;
                        n(document).off(Xt.FOCUSIN).on(Xt.FOCUSIN, function(e) {
                            document !== e.target && t._element !== e.target && 0 === n(t._element).has(e.target).length && t._element.focus()
                        })
                    }, e._setEscapeEvent = function() {
                        var t = this;
                        this._isShown && this._config.keyboard ? n(this._element).on(Xt.KEYDOWN_DISMISS, function(e) {
                            27 === e.which && (e.preventDefault(), t.hide())
                        }) : this._isShown || n(this._element).off(Xt.KEYDOWN_DISMISS)
                    }, e._setResizeEvent = function() {
                        var t = this;
                        this._isShown ? n(window).on(Xt.RESIZE, function(e) {
                            return t.handleUpdate(e)
                        }) : n(window).off(Xt.RESIZE)
                    }, e._hideModal = function() {
                        var t = this;
                        this._element.style.display = "none", this._element.setAttribute("aria-hidden", !0), this._element.removeAttribute("aria-modal"), this._isTransitioning = !1, this._showBackdrop(function() {
                            n(document.body).removeClass(zt.OPEN), t._resetAdjustments(), t._resetScrollbar(), n(t._element).trigger(Xt.HIDDEN)
                        })
                    }, e._removeBackdrop = function() {
                        this._backdrop && (n(this._backdrop).remove(), this._backdrop = null)
                    }, e._showBackdrop = function(t) {
                        var e = this,
                            i = n(this._element).hasClass(zt.FADE) ? zt.FADE : "";
                        if (this._isShown && this._config.backdrop) {
                            if (this._backdrop = document.createElement("div"), this._backdrop.className = zt.BACKDROP, i && this._backdrop.classList.add(i), n(this._backdrop).appendTo(document.body), n(this._element).on(Xt.CLICK_DISMISS, function(t) {
                                    e._ignoreBackdropClick ? e._ignoreBackdropClick = !1 : t.target === t.currentTarget && ("static" === e._config.backdrop ? e._element.focus() : e.hide())
                                }), i && c.reflow(this._backdrop), n(this._backdrop).addClass(zt.SHOW), !t) return;
                            if (!i) return void t();
                            var o = c.getTransitionDurationFromElement(this._backdrop);
                            n(this._backdrop).one(c.TRANSITION_END, t).emulateTransitionEnd(o)
                        } else if (!this._isShown && this._backdrop) {
                            n(this._backdrop).removeClass(zt.SHOW);
                            var r = function() {
                                e._removeBackdrop(), t && t()
                            };
                            if (n(this._element).hasClass(zt.FADE)) {
                                var s = c.getTransitionDurationFromElement(this._backdrop);
                                n(this._backdrop).one(c.TRANSITION_END, r).emulateTransitionEnd(s)
                            } else r()
                        } else t && t()
                    }, e._adjustDialog = function() {
                        var t = this._element.scrollHeight > document.documentElement.clientHeight;
                        !this._isBodyOverflowing && t && (this._element.style.paddingLeft = this._scrollbarWidth + "px"), this._isBodyOverflowing && !t && (this._element.style.paddingRight = this._scrollbarWidth + "px")
                    }, e._resetAdjustments = function() {
                        this._element.style.paddingLeft = "", this._element.style.paddingRight = ""
                    }, e._checkScrollbar = function() {
                        var t = document.body.getBoundingClientRect();
                        this._isBodyOverflowing = t.left + t.right < window.innerWidth, this._scrollbarWidth = this._getScrollbarWidth()
                    }, e._setScrollbar = function() {
                        var t = this;
                        if (this._isBodyOverflowing) {
                            var e = [].slice.call(document.querySelectorAll($t.FIXED_CONTENT)),
                                i = [].slice.call(document.querySelectorAll($t.STICKY_CONTENT));
                            n(e).each(function(e, i) {
                                var o = i.style.paddingRight,
                                    r = n(i).css("padding-right");
                                n(i).data("padding-right", o).css("padding-right", parseFloat(r) + t._scrollbarWidth + "px")
                            }), n(i).each(function(e, i) {
                                var o = i.style.marginRight,
                                    r = n(i).css("margin-right");
                                n(i).data("margin-right", o).css("margin-right", parseFloat(r) - t._scrollbarWidth + "px")
                            });
                            var o = document.body.style.paddingRight,
                                r = n(document.body).css("padding-right");
                            n(document.body).data("padding-right", o).css("padding-right", parseFloat(r) + this._scrollbarWidth + "px")
                        }
                        n(document.body).addClass(zt.OPEN)
                    }, e._resetScrollbar = function() {
                        var t = [].slice.call(document.querySelectorAll($t.FIXED_CONTENT));
                        n(t).each(function(t, e) {
                            var i = n(e).data("padding-right");
                            n(e).removeData("padding-right"), e.style.paddingRight = i || ""
                        });
                        var e = [].slice.call(document.querySelectorAll("" + $t.STICKY_CONTENT));
                        n(e).each(function(t, e) {
                            var i = n(e).data("margin-right");
                            void 0 !== i && n(e).css("margin-right", i).removeData("margin-right")
                        });
                        var i = n(document.body).data("padding-right");
                        n(document.body).removeData("padding-right"), document.body.style.paddingRight = i || ""
                    }, e._getScrollbarWidth = function() {
                        var t = document.createElement("div");
                        t.className = zt.SCROLLBAR_MEASURER, document.body.appendChild(t);
                        var e = t.getBoundingClientRect().width - t.clientWidth;
                        return document.body.removeChild(t), e
                    }, t._jQueryInterface = function(e, i) {
                        return this.each(function() {
                            var o = n(this).data("bs.modal"),
                                r = s({}, Qt, n(this).data(), "object" == typeof e && e ? e : {});
                            if (o || (o = new t(this, r), n(this).data("bs.modal", o)), "string" == typeof e) {
                                if (void 0 === o[e]) throw new TypeError('No method named "' + e + '"');
                                o[e](i)
                            } else r.show && o.show(i)
                        })
                    }, o(t, null, [{
                        key: "VERSION",
                        get: function() {
                            return "4.3.1"
                        }
                    }, {
                        key: "Default",
                        get: function() {
                            return Qt
                        }
                    }]), t
                }();
            n(document).on(Xt.CLICK_DATA_API, $t.DATA_TOGGLE, function(t) {
                var e, i = this,
                    o = c.getSelectorFromElement(this);
                o && (e = document.querySelector(o));
                var r = n(e).data("bs.modal") ? "toggle" : s({}, n(e).data(), n(this).data());
                "A" !== this.tagName && "AREA" !== this.tagName || t.preventDefault();
                var a = n(e).one(Xt.SHOW, function(t) {
                    t.isDefaultPrevented() || a.one(Xt.HIDDEN, function() {
                        n(i).is(":visible") && i.focus()
                    })
                });
                Jt._jQueryInterface.call(n(e), r, this)
            }), n.fn.modal = Jt._jQueryInterface, n.fn.modal.Constructor = Jt, n.fn.modal.noConflict = function() {
                return n.fn.modal = qt, Jt._jQueryInterface
            };
            var Zt = ["background", "cite", "href", "itemtype", "longdesc", "poster", "src", "xlink:href"],
                te = {
                    "*": ["class", "dir", "id", "lang", "role", /^aria-[\w-]*$/i],
                    a: ["target", "href", "title", "rel"],
                    area: [],
                    b: [],
                    br: [],
                    col: [],
                    code: [],
                    div: [],
                    em: [],
                    hr: [],
                    h1: [],
                    h2: [],
                    h3: [],
                    h4: [],
                    h5: [],
                    h6: [],
                    i: [],
                    img: ["src", "alt", "title", "width", "height"],
                    li: [],
                    ol: [],
                    p: [],
                    pre: [],
                    s: [],
                    small: [],
                    span: [],
                    sub: [],
                    sup: [],
                    strong: [],
                    u: [],
                    ul: []
                },
                ee = /^(?:(?:https?|mailto|ftp|tel|file):|[^&:/?#]*(?:[/?#]|$))/gi,
                ne = /^data:(?:image\/(?:bmp|gif|jpeg|jpg|png|tiff|webp)|video\/(?:mpeg|mp4|ogg|webm)|audio\/(?:mp3|oga|ogg|opus));base64,[a-z0-9+/]+=*$/i;

            function ie(t, e, n) {
                if (0 === t.length) return t;
                if (n && "function" == typeof n) return n(t);
                for (var i = new window.DOMParser, o = i.parseFromString(t, "text/html"), r = Object.keys(e), s = [].slice.call(o.body.querySelectorAll("*")), a = function(t, n) {
                        var i = s[t],
                            o = i.nodeName.toLowerCase();
                        if (-1 === r.indexOf(i.nodeName.toLowerCase())) return i.parentNode.removeChild(i), "continue";
                        var a = [].slice.call(i.attributes),
                            l = [].concat(e["*"] || [], e[o] || []);
                        a.forEach(function(t) {
                            (function(t, e) {
                                var n = t.nodeName.toLowerCase();
                                if (-1 !== e.indexOf(n)) return -1 === Zt.indexOf(n) || Boolean(t.nodeValue.match(ee) || t.nodeValue.match(ne));
                                for (var i = e.filter(function(t) {
                                        return t instanceof RegExp
                                    }), o = 0, r = i.length; o < r; o++)
                                    if (n.match(i[o])) return !0;
                                return !1
                            })(t, l) || i.removeAttribute(t.nodeName)
                        })
                    }, l = 0, c = s.length; l < c; l++) a(l);
                return o.body.innerHTML
            }
            var oe = "tooltip",
                re = n.fn.tooltip,
                se = new RegExp("(^|\\s)bs-tooltip\\S+", "g"),
                ae = ["sanitize", "whiteList", "sanitizeFn"],
                le = {
                    animation: "boolean",
                    template: "string",
                    title: "(string|element|function)",
                    trigger: "string",
                    delay: "(number|object)",
                    html: "boolean",
                    selector: "(string|boolean)",
                    placement: "(string|function)",
                    offset: "(number|string|function)",
                    container: "(string|element|boolean)",
                    fallbackPlacement: "(string|array)",
                    boundary: "(string|element)",
                    sanitize: "boolean",
                    sanitizeFn: "(null|function)",
                    whiteList: "object"
                },
                ce = {
                    AUTO: "auto",
                    TOP: "top",
                    RIGHT: "right",
                    BOTTOM: "bottom",
                    LEFT: "left"
                },
                ue = {
                    animation: !0,
                    template: '<div class="tooltip" role="tooltip"><div class="arrow"></div><div class="tooltip-inner"></div></div>',
                    trigger: "hover focus",
                    title: "",
                    delay: 0,
                    html: !1,
                    selector: !1,
                    placement: "top",
                    offset: 0,
                    container: !1,
                    fallbackPlacement: "flip",
                    boundary: "scrollParent",
                    sanitize: !0,
                    sanitizeFn: null,
                    whiteList: te
                },
                he = {
                    SHOW: "show",
                    OUT: "out"
                },
                fe = {
                    HIDE: "hide.bs.tooltip",
                    HIDDEN: "hidden.bs.tooltip",
                    SHOW: "show.bs.tooltip",
                    SHOWN: "shown.bs.tooltip",
                    INSERTED: "inserted.bs.tooltip",
                    CLICK: "click.bs.tooltip",
                    FOCUSIN: "focusin.bs.tooltip",
                    FOCUSOUT: "focusout.bs.tooltip",
                    MOUSEENTER: "mouseenter.bs.tooltip",
                    MOUSELEAVE: "mouseleave.bs.tooltip"
                },
                de = {
                    FADE: "fade",
                    SHOW: "show"
                },
                pe = {
                    TOOLTIP: ".tooltip",
                    TOOLTIP_INNER: ".tooltip-inner",
                    ARROW: ".arrow"
                },
                me = {
                    HOVER: "hover",
                    FOCUS: "focus",
                    CLICK: "click",
                    MANUAL: "manual"
                },
                ge = function() {
                    function t(t, e) {
                        if (void 0 === Wt) throw new TypeError("Bootstrap's tooltips require Popper.js (https://popper.js.org/)");
                        this._isEnabled = !0, this._timeout = 0, this._hoverState = "", this._activeTrigger = {}, this._popper = null, this.element = t, this.config = this._getConfig(e), this.tip = null, this._setListeners()
                    }
                    var e = t.prototype;
                    return e.enable = function() {
                        this._isEnabled = !0
                    }, e.disable = function() {
                        this._isEnabled = !1
                    }, e.toggleEnabled = function() {
                        this._isEnabled = !this._isEnabled
                    }, e.toggle = function(t) {
                        if (this._isEnabled)
                            if (t) {
                                var e = this.constructor.DATA_KEY,
                                    i = n(t.currentTarget).data(e);
                                i || (i = new this.constructor(t.currentTarget, this._getDelegateConfig()), n(t.currentTarget).data(e, i)), i._activeTrigger.click = !i._activeTrigger.click, i._isWithActiveTrigger() ? i._enter(null, i) : i._leave(null, i)
                            } else {
                                if (n(this.getTipElement()).hasClass(de.SHOW)) return void this._leave(null, this);
                                this._enter(null, this)
                            }
                    }, e.dispose = function() {
                        clearTimeout(this._timeout), n.removeData(this.element, this.constructor.DATA_KEY), n(this.element).off(this.constructor.EVENT_KEY), n(this.element).closest(".modal").off("hide.bs.modal"), this.tip && n(this.tip).remove(), this._isEnabled = null, this._timeout = null, this._hoverState = null, this._activeTrigger = null, null !== this._popper && this._popper.destroy(), this._popper = null, this.element = null, this.config = null, this.tip = null
                    }, e.show = function() {
                        var t = this;
                        if ("none" === n(this.element).css("display")) throw new Error("Please use show on visible elements");
                        var e = n.Event(this.constructor.Event.SHOW);
                        if (this.isWithContent() && this._isEnabled) {
                            n(this.element).trigger(e);
                            var i = c.findShadowRoot(this.element),
                                o = n.contains(null !== i ? i : this.element.ownerDocument.documentElement, this.element);
                            if (e.isDefaultPrevented() || !o) return;
                            var r = this.getTipElement(),
                                s = c.getUID(this.constructor.NAME);
                            r.setAttribute("id", s), this.element.setAttribute("aria-describedby", s), this.setContent(), this.config.animation && n(r).addClass(de.FADE);
                            var a = "function" == typeof this.config.placement ? this.config.placement.call(this, r, this.element) : this.config.placement,
                                l = this._getAttachment(a);
                            this.addAttachmentClass(l);
                            var u = this._getContainer();
                            n(r).data(this.constructor.DATA_KEY, this), n.contains(this.element.ownerDocument.documentElement, this.tip) || n(r).appendTo(u), n(this.element).trigger(this.constructor.Event.INSERTED), this._popper = new Wt(this.element, r, {
                                placement: l,
                                modifiers: {
                                    offset: this._getOffset(),
                                    flip: {
                                        behavior: this.config.fallbackPlacement
                                    },
                                    arrow: {
                                        element: pe.ARROW
                                    },
                                    preventOverflow: {
                                        boundariesElement: this.config.boundary
                                    }
                                },
                                onCreate: function(e) {
                                    e.originalPlacement !== e.placement && t._handlePopperPlacementChange(e)
                                },
                                onUpdate: function(e) {
                                    return t._handlePopperPlacementChange(e)
                                }
                            }), n(r).addClass(de.SHOW), "ontouchstart" in document.documentElement && n(document.body).children().on("mouseover", null, n.noop);
                            var h = function() {
                                t.config.animation && t._fixTransition();
                                var e = t._hoverState;
                                t._hoverState = null, n(t.element).trigger(t.constructor.Event.SHOWN), e === he.OUT && t._leave(null, t)
                            };
                            if (n(this.tip).hasClass(de.FADE)) {
                                var f = c.getTransitionDurationFromElement(this.tip);
                                n(this.tip).one(c.TRANSITION_END, h).emulateTransitionEnd(f)
                            } else h()
                        }
                    }, e.hide = function(t) {
                        var e = this,
                            i = this.getTipElement(),
                            o = n.Event(this.constructor.Event.HIDE),
                            r = function() {
                                e._hoverState !== he.SHOW && i.parentNode && i.parentNode.removeChild(i), e._cleanTipClass(), e.element.removeAttribute("aria-describedby"), n(e.element).trigger(e.constructor.Event.HIDDEN), null !== e._popper && e._popper.destroy(), t && t()
                            };
                        if (n(this.element).trigger(o), !o.isDefaultPrevented()) {
                            if (n(i).removeClass(de.SHOW), "ontouchstart" in document.documentElement && n(document.body).children().off("mouseover", null, n.noop), this._activeTrigger[me.CLICK] = !1, this._activeTrigger[me.FOCUS] = !1, this._activeTrigger[me.HOVER] = !1, n(this.tip).hasClass(de.FADE)) {
                                var s = c.getTransitionDurationFromElement(i);
                                n(i).one(c.TRANSITION_END, r).emulateTransitionEnd(s)
                            } else r();
                            this._hoverState = ""
                        }
                    }, e.update = function() {
                        null !== this._popper && this._popper.scheduleUpdate()
                    }, e.isWithContent = function() {
                        return Boolean(this.getTitle())
                    }, e.addAttachmentClass = function(t) {
                        n(this.getTipElement()).addClass("bs-tooltip-" + t)
                    }, e.getTipElement = function() {
                        return this.tip = this.tip || n(this.config.template)[0], this.tip
                    }, e.setContent = function() {
                        var t = this.getTipElement();
                        this.setElementContent(n(t.querySelectorAll(pe.TOOLTIP_INNER)), this.getTitle()), n(t).removeClass(de.FADE + " " + de.SHOW)
                    }, e.setElementContent = function(t, e) {
                        "object" != typeof e || !e.nodeType && !e.jquery ? this.config.html ? (this.config.sanitize && (e = ie(e, this.config.whiteList, this.config.sanitizeFn)), t.html(e)) : t.text(e) : this.config.html ? n(e).parent().is(t) || t.empty().append(e) : t.text(n(e).text())
                    }, e.getTitle = function() {
                        var t = this.element.getAttribute("data-original-title");
                        return t || (t = "function" == typeof this.config.title ? this.config.title.call(this.element) : this.config.title), t
                    }, e._getOffset = function() {
                        var t = this,
                            e = {};
                        return "function" == typeof this.config.offset ? e.fn = function(e) {
                            return e.offsets = s({}, e.offsets, t.config.offset(e.offsets, t.element) || {}), e
                        } : e.offset = this.config.offset, e
                    }, e._getContainer = function() {
                        return !1 === this.config.container ? document.body : c.isElement(this.config.container) ? n(this.config.container) : n(document).find(this.config.container)
                    }, e._getAttachment = function(t) {
                        return ce[t.toUpperCase()]
                    }, e._setListeners = function() {
                        var t = this,
                            e = this.config.trigger.split(" ");
                        e.forEach(function(e) {
                            if ("click" === e) n(t.element).on(t.constructor.Event.CLICK, t.config.selector, function(e) {
                                return t.toggle(e)
                            });
                            else if (e !== me.MANUAL) {
                                var i = e === me.HOVER ? t.constructor.Event.MOUSEENTER : t.constructor.Event.FOCUSIN,
                                    o = e === me.HOVER ? t.constructor.Event.MOUSELEAVE : t.constructor.Event.FOCUSOUT;
                                n(t.element).on(i, t.config.selector, function(e) {
                                    return t._enter(e)
                                }).on(o, t.config.selector, function(e) {
                                    return t._leave(e)
                                })
                            }
                        }), n(this.element).closest(".modal").on("hide.bs.modal", function() {
                            t.element && t.hide()
                        }), this.config.selector ? this.config = s({}, this.config, {
                            trigger: "manual",
                            selector: ""
                        }) : this._fixTitle()
                    }, e._fixTitle = function() {
                        var t = typeof this.element.getAttribute("data-original-title");
                        (this.element.getAttribute("title") || "string" !== t) && (this.element.setAttribute("data-original-title", this.element.getAttribute("title") || ""), this.element.setAttribute("title", ""))
                    }, e._enter = function(t, e) {
                        var i = this.constructor.DATA_KEY;
                        (e = e || n(t.currentTarget).data(i)) || (e = new this.constructor(t.currentTarget, this._getDelegateConfig()), n(t.currentTarget).data(i, e)), t && (e._activeTrigger["focusin" === t.type ? me.FOCUS : me.HOVER] = !0), n(e.getTipElement()).hasClass(de.SHOW) || e._hoverState === he.SHOW ? e._hoverState = he.SHOW : (clearTimeout(e._timeout), e._hoverState = he.SHOW, e.config.delay && e.config.delay.show ? e._timeout = setTimeout(function() {
                            e._hoverState === he.SHOW && e.show()
                        }, e.config.delay.show) : e.show())
                    }, e._leave = function(t, e) {
                        var i = this.constructor.DATA_KEY;
                        (e = e || n(t.currentTarget).data(i)) || (e = new this.constructor(t.currentTarget, this._getDelegateConfig()), n(t.currentTarget).data(i, e)), t && (e._activeTrigger["focusout" === t.type ? me.FOCUS : me.HOVER] = !1), e._isWithActiveTrigger() || (clearTimeout(e._timeout), e._hoverState = he.OUT, e.config.delay && e.config.delay.hide ? e._timeout = setTimeout(function() {
                            e._hoverState === he.OUT && e.hide()
                        }, e.config.delay.hide) : e.hide())
                    }, e._isWithActiveTrigger = function() {
                        for (var t in this._activeTrigger)
                            if (this._activeTrigger[t]) return !0;
                        return !1
                    }, e._getConfig = function(t) {
                        var e = n(this.element).data();
                        return Object.keys(e).forEach(function(t) {
                            -1 !== ae.indexOf(t) && delete e[t]
                        }), "number" == typeof(t = s({}, this.constructor.Default, e, "object" == typeof t && t ? t : {})).delay && (t.delay = {
                            show: t.delay,
                            hide: t.delay
                        }), "number" == typeof t.title && (t.title = t.title.toString()), "number" == typeof t.content && (t.content = t.content.toString()), c.typeCheckConfig(oe, t, this.constructor.DefaultType), t.sanitize && (t.template = ie(t.template, t.whiteList, t.sanitizeFn)), t
                    }, e._getDelegateConfig = function() {
                        var t = {};
                        if (this.config)
                            for (var e in this.config) this.constructor.Default[e] !== this.config[e] && (t[e] = this.config[e]);
                        return t
                    }, e._cleanTipClass = function() {
                        var t = n(this.getTipElement()),
                            e = t.attr("class").match(se);
                        null !== e && e.length && t.removeClass(e.join(""))
                    }, e._handlePopperPlacementChange = function(t) {
                        var e = t.instance;
                        this.tip = e.popper, this._cleanTipClass(), this.addAttachmentClass(this._getAttachment(t.placement))
                    }, e._fixTransition = function() {
                        var t = this.getTipElement(),
                            e = this.config.animation;
                        null === t.getAttribute("x-placement") && (n(t).removeClass(de.FADE), this.config.animation = !1, this.hide(), this.show(), this.config.animation = e)
                    }, t._jQueryInterface = function(e) {
                        return this.each(function() {
                            var i = n(this).data("bs.tooltip"),
                                o = "object" == typeof e && e;
                            if ((i || !/dispose|hide/.test(e)) && (i || (i = new t(this, o), n(this).data("bs.tooltip", i)), "string" == typeof e)) {
                                if (void 0 === i[e]) throw new TypeError('No method named "' + e + '"');
                                i[e]()
                            }
                        })
                    }, o(t, null, [{
                        key: "VERSION",
                        get: function() {
                            return "4.3.1"
                        }
                    }, {
                        key: "Default",
                        get: function() {
                            return ue
                        }
                    }, {
                        key: "NAME",
                        get: function() {
                            return oe
                        }
                    }, {
                        key: "DATA_KEY",
                        get: function() {
                            return "bs.tooltip"
                        }
                    }, {
                        key: "Event",
                        get: function() {
                            return fe
                        }
                    }, {
                        key: "EVENT_KEY",
                        get: function() {
                            return ".bs.tooltip"
                        }
                    }, {
                        key: "DefaultType",
                        get: function() {
                            return le
                        }
                    }]), t
                }();
            n.fn.tooltip = ge._jQueryInterface, n.fn.tooltip.Constructor = ge, n.fn.tooltip.noConflict = function() {
                return n.fn.tooltip = re, ge._jQueryInterface
            };
            var _e = "popover",
                ve = n.fn.popover,
                Ee = new RegExp("(^|\\s)bs-popover\\S+", "g"),
                Te = s({}, ge.Default, {
                    placement: "right",
                    trigger: "click",
                    content: "",
                    template: '<div class="popover" role="tooltip"><div class="arrow"></div><h3 class="popover-header"></h3><div class="popover-body"></div></div>'
                }),
                be = s({}, ge.DefaultType, {
                    content: "(string|element|function)"
                }),
                ye = {
                    FADE: "fade",
                    SHOW: "show"
                },
                Se = {
                    TITLE: ".popover-header",
                    CONTENT: ".popover-body"
                },
                Oe = {
                    HIDE: "hide.bs.popover",
                    HIDDEN: "hidden.bs.popover",
                    SHOW: "show.bs.popover",
                    SHOWN: "shown.bs.popover",
                    INSERTED: "inserted.bs.popover",
                    CLICK: "click.bs.popover",
                    FOCUSIN: "focusin.bs.popover",
                    FOCUSOUT: "focusout.bs.popover",
                    MOUSEENTER: "mouseenter.bs.popover",
                    MOUSELEAVE: "mouseleave.bs.popover"
                },
                Ie = function(t) {
                    var e, i;

                    function r() {
                        return t.apply(this, arguments) || this
                    }
                    i = t, (e = r).prototype = Object.create(i.prototype), e.prototype.constructor = e, e.__proto__ = i;
                    var s = r.prototype;
                    return s.isWithContent = function() {
                        return this.getTitle() || this._getContent()
                    }, s.addAttachmentClass = function(t) {
                        n(this.getTipElement()).addClass("bs-popover-" + t)
                    }, s.getTipElement = function() {
                        return this.tip = this.tip || n(this.config.template)[0], this.tip
                    }, s.setContent = function() {
                        var t = n(this.getTipElement());
                        this.setElementContent(t.find(Se.TITLE), this.getTitle());
                        var e = this._getContent();
                        "function" == typeof e && (e = e.call(this.element)), this.setElementContent(t.find(Se.CONTENT), e), t.removeClass(ye.FADE + " " + ye.SHOW)
                    }, s._getContent = function() {
                        return this.element.getAttribute("data-content") || this.config.content
                    }, s._cleanTipClass = function() {
                        var t = n(this.getTipElement()),
                            e = t.attr("class").match(Ee);
                        null !== e && e.length > 0 && t.removeClass(e.join(""))
                    }, r._jQueryInterface = function(t) {
                        return this.each(function() {
                            var e = n(this).data("bs.popover"),
                                i = "object" == typeof t ? t : null;
                            if ((e || !/dispose|hide/.test(t)) && (e || (e = new r(this, i), n(this).data("bs.popover", e)), "string" == typeof t)) {
                                if (void 0 === e[t]) throw new TypeError('No method named "' + t + '"');
                                e[t]()
                            }
                        })
                    }, o(r, null, [{
                        key: "VERSION",
                        get: function() {
                            return "4.3.1"
                        }
                    }, {
                        key: "Default",
                        get: function() {
                            return Te
                        }
                    }, {
                        key: "NAME",
                        get: function() {
                            return _e
                        }
                    }, {
                        key: "DATA_KEY",
                        get: function() {
                            return "bs.popover"
                        }
                    }, {
                        key: "Event",
                        get: function() {
                            return Oe
                        }
                    }, {
                        key: "EVENT_KEY",
                        get: function() {
                            return ".bs.popover"
                        }
                    }, {
                        key: "DefaultType",
                        get: function() {
                            return be
                        }
                    }]), r
                }(ge);
            n.fn.popover = Ie._jQueryInterface, n.fn.popover.Constructor = Ie, n.fn.popover.noConflict = function() {
                return n.fn.popover = ve, Ie._jQueryInterface
            };
            var Ce = "scrollspy",
                Ae = n.fn[Ce],
                De = {
                    offset: 10,
                    method: "auto",
                    target: ""
                },
                we = {
                    offset: "number",
                    method: "string",
                    target: "(string|element)"
                },
                Ne = {
                    ACTIVATE: "activate.bs.scrollspy",
                    SCROLL: "scroll.bs.scrollspy",
                    LOAD_DATA_API: "load.bs.scrollspy.data-api"
                },
                Le = {
                    DROPDOWN_ITEM: "dropdown-item",
                    DROPDOWN_MENU: "dropdown-menu",
                    ACTIVE: "active"
                },
                Pe = {
                    DATA_SPY: '[data-spy="scroll"]',
                    ACTIVE: ".active",
                    NAV_LIST_GROUP: ".nav, .list-group",
                    NAV_LINKS: ".nav-link",
                    NAV_ITEMS: ".nav-item",
                    LIST_ITEMS: ".list-group-item",
                    DROPDOWN: ".dropdown",
                    DROPDOWN_ITEMS: ".dropdown-item",
                    DROPDOWN_TOGGLE: ".dropdown-toggle"
                },
                He = {
                    OFFSET: "offset",
                    POSITION: "position"
                },
                Re = function() {
                    function t(t, e) {
                        var i = this;
                        this._element = t, this._scrollElement = "BODY" === t.tagName ? window : t, this._config = this._getConfig(e), this._selector = this._config.target + " " + Pe.NAV_LINKS + "," + this._config.target + " " + Pe.LIST_ITEMS + "," + this._config.target + " " + Pe.DROPDOWN_ITEMS, this._offsets = [], this._targets = [], this._activeTarget = null, this._scrollHeight = 0, n(this._scrollElement).on(Ne.SCROLL, function(t) {
                            return i._process(t)
                        }), this.refresh(), this._process()
                    }
                    var e = t.prototype;
                    return e.refresh = function() {
                        var t = this,
                            e = this._scrollElement === this._scrollElement.window ? He.OFFSET : He.POSITION,
                            i = "auto" === this._config.method ? e : this._config.method,
                            o = i === He.POSITION ? this._getScrollTop() : 0;
                        this._offsets = [], this._targets = [], this._scrollHeight = this._getScrollHeight();
                        var r = [].slice.call(document.querySelectorAll(this._selector));
                        r.map(function(t) {
                            var e, r = c.getSelectorFromElement(t);
                            if (r && (e = document.querySelector(r)), e) {
                                var s = e.getBoundingClientRect();
                                if (s.width || s.height) return [n(e)[i]().top + o, r]
                            }
                            return null
                        }).filter(function(t) {
                            return t
                        }).sort(function(t, e) {
                            return t[0] - e[0]
                        }).forEach(function(e) {
                            t._offsets.push(e[0]), t._targets.push(e[1])
                        })
                    }, e.dispose = function() {
                        n.removeData(this._element, "bs.scrollspy"), n(this._scrollElement).off(".bs.scrollspy"), this._element = null, this._scrollElement = null, this._config = null, this._selector = null, this._offsets = null, this._targets = null, this._activeTarget = null, this._scrollHeight = null
                    }, e._getConfig = function(t) {
                        if ("string" != typeof(t = s({}, De, "object" == typeof t && t ? t : {})).target) {
                            var e = n(t.target).attr("id");
                            e || (e = c.getUID(Ce), n(t.target).attr("id", e)), t.target = "#" + e
                        }
                        return c.typeCheckConfig(Ce, t, we), t
                    }, e._getScrollTop = function() {
                        return this._scrollElement === window ? this._scrollElement.pageYOffset : this._scrollElement.scrollTop
                    }, e._getScrollHeight = function() {
                        return this._scrollElement.scrollHeight || Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)
                    }, e._getOffsetHeight = function() {
                        return this._scrollElement === window ? window.innerHeight : this._scrollElement.getBoundingClientRect().height
                    }, e._process = function() {
                        var t = this._getScrollTop() + this._config.offset,
                            e = this._getScrollHeight(),
                            n = this._config.offset + e - this._getOffsetHeight();
                        if (this._scrollHeight !== e && this.refresh(), t >= n) {
                            var i = this._targets[this._targets.length - 1];
                            this._activeTarget !== i && this._activate(i)
                        } else {
                            if (this._activeTarget && t < this._offsets[0] && this._offsets[0] > 0) return this._activeTarget = null, void this._clear();
                            for (var o = this._offsets.length, r = o; r--;) {
                                var s = this._activeTarget !== this._targets[r] && t >= this._offsets[r] && (void 0 === this._offsets[r + 1] || t < this._offsets[r + 1]);
                                s && this._activate(this._targets[r])
                            }
                        }
                    }, e._activate = function(t) {
                        this._activeTarget = t, this._clear();
                        var e = this._selector.split(",").map(function(e) {
                                return e + '[data-target="' + t + '"],' + e + '[href="' + t + '"]'
                            }),
                            i = n([].slice.call(document.querySelectorAll(e.join(","))));
                        i.hasClass(Le.DROPDOWN_ITEM) ? (i.closest(Pe.DROPDOWN).find(Pe.DROPDOWN_TOGGLE).addClass(Le.ACTIVE), i.addClass(Le.ACTIVE)) : (i.addClass(Le.ACTIVE), i.parents(Pe.NAV_LIST_GROUP).prev(Pe.NAV_LINKS + ", " + Pe.LIST_ITEMS).addClass(Le.ACTIVE), i.parents(Pe.NAV_LIST_GROUP).prev(Pe.NAV_ITEMS).children(Pe.NAV_LINKS).addClass(Le.ACTIVE)), n(this._scrollElement).trigger(Ne.ACTIVATE, {
                            relatedTarget: t
                        })
                    }, e._clear = function() {
                        [].slice.call(document.querySelectorAll(this._selector)).filter(function(t) {
                            return t.classList.contains(Le.ACTIVE)
                        }).forEach(function(t) {
                            return t.classList.remove(Le.ACTIVE)
                        })
                    }, t._jQueryInterface = function(e) {
                        return this.each(function() {
                            var i = n(this).data("bs.scrollspy"),
                                o = "object" == typeof e && e;
                            if (i || (i = new t(this, o), n(this).data("bs.scrollspy", i)), "string" == typeof e) {
                                if (void 0 === i[e]) throw new TypeError('No method named "' + e + '"');
                                i[e]()
                            }
                        })
                    }, o(t, null, [{
                        key: "VERSION",
                        get: function() {
                            return "4.3.1"
                        }
                    }, {
                        key: "Default",
                        get: function() {
                            return De
                        }
                    }]), t
                }();
            n(window).on(Ne.LOAD_DATA_API, function() {
                for (var t = [].slice.call(document.querySelectorAll(Pe.DATA_SPY)), e = t.length, i = e; i--;) {
                    var o = n(t[i]);
                    Re._jQueryInterface.call(o, o.data())
                }
            }), n.fn[Ce] = Re._jQueryInterface, n.fn[Ce].Constructor = Re, n.fn[Ce].noConflict = function() {
                return n.fn[Ce] = Ae, Re._jQueryInterface
            };
            var We = n.fn.tab,
                ke = {
                    HIDE: "hide.bs.tab",
                    HIDDEN: "hidden.bs.tab",
                    SHOW: "show.bs.tab",
                    SHOWN: "shown.bs.tab",
                    CLICK_DATA_API: "click.bs.tab.data-api"
                },
                Fe = {
                    DROPDOWN_MENU: "dropdown-menu",
                    ACTIVE: "active",
                    DISABLED: "disabled",
                    FADE: "fade",
                    SHOW: "show"
                },
                Me = {
                    DROPDOWN: ".dropdown",
                    NAV_LIST_GROUP: ".nav, .list-group",
                    ACTIVE: ".active",
                    ACTIVE_UL: "> li > .active",
                    DATA_TOGGLE: '[data-toggle="tab"], [data-toggle="pill"], [data-toggle="list"]',
                    DROPDOWN_TOGGLE: ".dropdown-toggle",
                    DROPDOWN_ACTIVE_CHILD: "> .dropdown-menu .active"
                },
                xe = function() {
                    function t(t) {
                        this._element = t
                    }
                    var e = t.prototype;
                    return e.show = function() {
                        var t = this;
                        if (!(this._element.parentNode && this._element.parentNode.nodeType === Node.ELEMENT_NODE && n(this._element).hasClass(Fe.ACTIVE) || n(this._element).hasClass(Fe.DISABLED))) {
                            var e, i, o = n(this._element).closest(Me.NAV_LIST_GROUP)[0],
                                r = c.getSelectorFromElement(this._element);
                            if (o) {
                                var s = "UL" === o.nodeName || "OL" === o.nodeName ? Me.ACTIVE_UL : Me.ACTIVE;
                                i = (i = n.makeArray(n(o).find(s)))[i.length - 1]
                            }
                            var a = n.Event(ke.HIDE, {
                                    relatedTarget: this._element
                                }),
                                l = n.Event(ke.SHOW, {
                                    relatedTarget: i
                                });
                            if (i && n(i).trigger(a), n(this._element).trigger(l), !l.isDefaultPrevented() && !a.isDefaultPrevented()) {
                                r && (e = document.querySelector(r)), this._activate(this._element, o);
                                var u = function() {
                                    var e = n.Event(ke.HIDDEN, {
                                            relatedTarget: t._element
                                        }),
                                        o = n.Event(ke.SHOWN, {
                                            relatedTarget: i
                                        });
                                    n(i).trigger(e), n(t._element).trigger(o)
                                };
                                e ? this._activate(e, e.parentNode, u) : u()
                            }
                        }
                    }, e.dispose = function() {
                        n.removeData(this._element, "bs.tab"), this._element = null
                    }, e._activate = function(t, e, i) {
                        var o = this,
                            r = !e || "UL" !== e.nodeName && "OL" !== e.nodeName ? n(e).children(Me.ACTIVE) : n(e).find(Me.ACTIVE_UL),
                            s = r[0],
                            a = i && s && n(s).hasClass(Fe.FADE),
                            l = function() {
                                return o._transitionComplete(t, s, i)
                            };
                        if (s && a) {
                            var u = c.getTransitionDurationFromElement(s);
                            n(s).removeClass(Fe.SHOW).one(c.TRANSITION_END, l).emulateTransitionEnd(u)
                        } else l()
                    }, e._transitionComplete = function(t, e, i) {
                        if (e) {
                            n(e).removeClass(Fe.ACTIVE);
                            var o = n(e.parentNode).find(Me.DROPDOWN_ACTIVE_CHILD)[0];
                            o && n(o).removeClass(Fe.ACTIVE), "tab" === e.getAttribute("role") && e.setAttribute("aria-selected", !1)
                        }
                        if (n(t).addClass(Fe.ACTIVE), "tab" === t.getAttribute("role") && t.setAttribute("aria-selected", !0), c.reflow(t), t.classList.contains(Fe.FADE) && t.classList.add(Fe.SHOW), t.parentNode && n(t.parentNode).hasClass(Fe.DROPDOWN_MENU)) {
                            var r = n(t).closest(Me.DROPDOWN)[0];
                            if (r) {
                                var s = [].slice.call(r.querySelectorAll(Me.DROPDOWN_TOGGLE));
                                n(s).addClass(Fe.ACTIVE)
                            }
                            t.setAttribute("aria-expanded", !0)
                        }
                        i && i()
                    }, t._jQueryInterface = function(e) {
                        return this.each(function() {
                            var i = n(this),
                                o = i.data("bs.tab");
                            if (o || (o = new t(this), i.data("bs.tab", o)), "string" == typeof e) {
                                if (void 0 === o[e]) throw new TypeError('No method named "' + e + '"');
                                o[e]()
                            }
                        })
                    }, o(t, null, [{
                        key: "VERSION",
                        get: function() {
                            return "4.3.1"
                        }
                    }]), t
                }();
            n(document).on(ke.CLICK_DATA_API, Me.DATA_TOGGLE, function(t) {
                t.preventDefault(), xe._jQueryInterface.call(n(this), "show")
            }), n.fn.tab = xe._jQueryInterface, n.fn.tab.Constructor = xe, n.fn.tab.noConflict = function() {
                return n.fn.tab = We, xe._jQueryInterface
            };
            var Ue = n.fn.toast,
                Ve = {
                    CLICK_DISMISS: "click.dismiss.bs.toast",
                    HIDE: "hide.bs.toast",
                    HIDDEN: "hidden.bs.toast",
                    SHOW: "show.bs.toast",
                    SHOWN: "shown.bs.toast"
                },
                je = {
                    FADE: "fade",
                    HIDE: "hide",
                    SHOW: "show",
                    SHOWING: "showing"
                },
                Be = {
                    animation: "boolean",
                    autohide: "boolean",
                    delay: "number"
                },
                Ge = {
                    animation: !0,
                    autohide: !0,
                    delay: 500
                },
                Ke = {
                    DATA_DISMISS: '[data-dismiss="toast"]'
                },
                qe = function() {
                    function t(t, e) {
                        this._element = t, this._config = this._getConfig(e), this._timeout = null, this._setListeners()
                    }
                    var e = t.prototype;
                    return e.show = function() {
                        var t = this;
                        n(this._element).trigger(Ve.SHOW), this._config.animation && this._element.classList.add(je.FADE);
                        var e = function() {
                            t._element.classList.remove(je.SHOWING), t._element.classList.add(je.SHOW), n(t._element).trigger(Ve.SHOWN), t._config.autohide && t.hide()
                        };
                        if (this._element.classList.remove(je.HIDE), this._element.classList.add(je.SHOWING), this._config.animation) {
                            var i = c.getTransitionDurationFromElement(this._element);
                            n(this._element).one(c.TRANSITION_END, e).emulateTransitionEnd(i)
                        } else e()
                    }, e.hide = function(t) {
                        var e = this;
                        this._element.classList.contains(je.SHOW) && (n(this._element).trigger(Ve.HIDE), t ? this._close() : this._timeout = setTimeout(function() {
                            e._close()
                        }, this._config.delay))
                    }, e.dispose = function() {
                        clearTimeout(this._timeout), this._timeout = null, this._element.classList.contains(je.SHOW) && this._element.classList.remove(je.SHOW), n(this._element).off(Ve.CLICK_DISMISS), n.removeData(this._element, "bs.toast"), this._element = null, this._config = null
                    }, e._getConfig = function(t) {
                        return t = s({}, Ge, n(this._element).data(), "object" == typeof t && t ? t : {}), c.typeCheckConfig("toast", t, this.constructor.DefaultType), t
                    }, e._setListeners = function() {
                        var t = this;
                        n(this._element).on(Ve.CLICK_DISMISS, Ke.DATA_DISMISS, function() {
                            return t.hide(!0)
                        })
                    }, e._close = function() {
                        var t = this,
                            e = function() {
                                t._element.classList.add(je.HIDE), n(t._element).trigger(Ve.HIDDEN)
                            };
                        if (this._element.classList.remove(je.SHOW), this._config.animation) {
                            var i = c.getTransitionDurationFromElement(this._element);
                            n(this._element).one(c.TRANSITION_END, e).emulateTransitionEnd(i)
                        } else e()
                    }, t._jQueryInterface = function(e) {
                        return this.each(function() {
                            var i = n(this),
                                o = i.data("bs.toast"),
                                r = "object" == typeof e && e;
                            if (o || (o = new t(this, r), i.data("bs.toast", o)), "string" == typeof e) {
                                if (void 0 === o[e]) throw new TypeError('No method named "' + e + '"');
                                o[e](this)
                            }
                        })
                    }, o(t, null, [{
                        key: "VERSION",
                        get: function() {
                            return "4.3.1"
                        }
                    }, {
                        key: "DefaultType",
                        get: function() {
                            return Be
                        }
                    }, {
                        key: "Default",
                        get: function() {
                            return Ge
                        }
                    }]), t
                }();
            n.fn.toast = qe._jQueryInterface, n.fn.toast.Constructor = qe, n.fn.toast.noConflict = function() {
                    return n.fn.toast = Ue, qe._jQueryInterface
                },
                function() {
                    if (void 0 === n) throw new TypeError("Bootstrap's JavaScript requires jQuery. jQuery must be included before Bootstrap's JavaScript.");
                    var t = n.fn.jquery.split(" ")[0].split(".");
                    if (t[0] < 2 && t[1] < 9 || 1 === t[0] && 9 === t[1] && t[2] < 1 || t[0] >= 4) throw new Error("Bootstrap's JavaScript requires at least jQuery v1.9.1 but less than v4.0.0")
                }(), t.Util = c, t.Alert = d, t.Button = v, t.Carousel = w, t.Collapse = M, t.Dropdown = Kt, t.Modal = Jt, t.Popover = Ie, t.Scrollspy = Re, t.Tab = xe, t.Toast = qe, t.Tooltip = ge, Object.defineProperty(t, "__esModule", {
                    value: !0
                })
        }(i, t)
    }(n = {
        exports: {}
    }, n.exports), n.exports);
    (i = o) && i.__esModule && Object.prototype.hasOwnProperty.call(i, "default") && i.default, $(".dropdown-menu a.dropdown-toggle").on("click", function(t) {
        return t.preventDefault(), t.stopImmediatePropagation(), $(this).next().hasClass("show") || $(this).parents(".dropdown-menu").first().find(".show").removeClass("show"), $(this).next(".dropdown-menu").toggleClass("show"), $(this).parents("li.nav-item.dropdown.show").on("hidden.bs.dropdown", function(t) {
            $(".dropdown-submenu .show").removeClass("show")
        }), !1
    })
}(window.jQuery);
//# sourceMappingURL=rigpl-theme.js.map
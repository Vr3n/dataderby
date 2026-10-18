"use strict";
(() => {
  // ../../node_modules/.pnpm/tslib@2.8.1/node_modules/tslib/tslib.es6.mjs
  var extendStatics = function(d, b) {
    extendStatics = Object.setPrototypeOf || { __proto__: [] } instanceof Array && function(d2, b2) {
      d2.__proto__ = b2;
    } || function(d2, b2) {
      for (var p in b2) if (Object.prototype.hasOwnProperty.call(b2, p)) d2[p] = b2[p];
    };
    return extendStatics(d, b);
  };
  function __extends(d, b) {
    if (typeof b !== "function" && b !== null)
      throw new TypeError("Class extends value " + String(b) + " is not a constructor or null");
    extendStatics(d, b);
    function __() {
      this.constructor = d;
    }
    d.prototype = b === null ? Object.create(b) : (__.prototype = b.prototype, new __());
  }
  var __assign = function() {
    __assign = Object.assign || function __assign2(t2) {
      for (var s, i2 = 1, n2 = arguments.length; i2 < n2; i2++) {
        s = arguments[i2];
        for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p)) t2[p] = s[p];
      }
      return t2;
    };
    return __assign.apply(this, arguments);
  };
  function __awaiter(thisArg, _arguments, P, generator) {
    function adopt(value) {
      return value instanceof P ? value : new P(function(resolve) {
        resolve(value);
      });
    }
    return new (P || (P = Promise))(function(resolve, reject) {
      function fulfilled(value) {
        try {
          step(generator.next(value));
        } catch (e2) {
          reject(e2);
        }
      }
      function rejected(value) {
        try {
          step(generator["throw"](value));
        } catch (e2) {
          reject(e2);
        }
      }
      function step(result) {
        result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
      }
      step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
  }
  function __generator(thisArg, body) {
    var _ = { label: 0, sent: function() {
      if (t2[0] & 1) throw t2[1];
      return t2[1];
    }, trys: [], ops: [] }, f, y, t2, g = Object.create((typeof Iterator === "function" ? Iterator : Object).prototype);
    return g.next = verb(0), g["throw"] = verb(1), g["return"] = verb(2), typeof Symbol === "function" && (g[Symbol.iterator] = function() {
      return this;
    }), g;
    function verb(n2) {
      return function(v) {
        return step([n2, v]);
      };
    }
    function step(op) {
      if (f) throw new TypeError("Generator is already executing.");
      while (g && (g = 0, op[0] && (_ = 0)), _) try {
        if (f = 1, y && (t2 = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t2 = y["return"]) && t2.call(y), 0) : y.next) && !(t2 = t2.call(y, op[1])).done) return t2;
        if (y = 0, t2) op = [op[0] & 2, t2.value];
        switch (op[0]) {
          case 0:
          case 1:
            t2 = op;
            break;
          case 4:
            _.label++;
            return { value: op[1], done: false };
          case 5:
            _.label++;
            y = op[1];
            op = [0];
            continue;
          case 7:
            op = _.ops.pop();
            _.trys.pop();
            continue;
          default:
            if (!(t2 = _.trys, t2 = t2.length > 0 && t2[t2.length - 1]) && (op[0] === 6 || op[0] === 2)) {
              _ = 0;
              continue;
            }
            if (op[0] === 3 && (!t2 || op[1] > t2[0] && op[1] < t2[3])) {
              _.label = op[1];
              break;
            }
            if (op[0] === 6 && _.label < t2[1]) {
              _.label = t2[1];
              t2 = op;
              break;
            }
            if (t2 && _.label < t2[2]) {
              _.label = t2[2];
              _.ops.push(op);
              break;
            }
            if (t2[2]) _.ops.pop();
            _.trys.pop();
            continue;
        }
        op = body.call(thisArg, _);
      } catch (e2) {
        op = [6, e2];
        y = 0;
      } finally {
        f = t2 = 0;
      }
      if (op[0] & 5) throw op[1];
      return { value: op[0] ? op[1] : void 0, done: true };
    }
  }
  function __spreadArray(to, from, pack) {
    if (pack || arguments.length === 2) for (var i2 = 0, l = from.length, ar; i2 < l; i2++) {
      if (ar || !(i2 in from)) {
        if (!ar) ar = Array.prototype.slice.call(from, 0, i2);
        ar[i2] = from[i2];
      }
    }
    return to.concat(ar || Array.prototype.slice.call(from));
  }

  // ../../node_modules/.pnpm/@fingerprintjs+botd@1.9.1/node_modules/@fingerprintjs/botd/dist/botd.esm.js
  var version = "1.9.1";
  var BotKind = {
    // Object is used instead of Typescript enum to avoid emitting IIFE which might be affected by further tree-shaking.
    // See example of compiled enums https://stackoverflow.com/q/47363996)
    Awesomium: "awesomium",
    Cef: "cef",
    CefSharp: "cefsharp",
    CoachJS: "coachjs",
    Electron: "electron",
    FMiner: "fminer",
    Geb: "geb",
    NightmareJS: "nightmarejs",
    Phantomas: "phantomas",
    PhantomJS: "phantomjs",
    Rhino: "rhino",
    Selenium: "selenium",
    Sequentum: "sequentum",
    SlimerJS: "slimerjs",
    WebDriverIO: "webdriverio",
    WebDriver: "webdriver",
    HeadlessChrome: "headless_chrome",
    Unknown: "unknown"
  };
  var BotdError = (
    /** @class */
    function(_super) {
      __extends(BotdError2, _super);
      function BotdError2(state, message) {
        var _this = _super.call(this, message) || this;
        _this.state = state;
        _this.name = "BotdError";
        Object.setPrototypeOf(_this, BotdError2.prototype);
        return _this;
      }
      return BotdError2;
    }(Error)
  );
  function detect(components, detectors2) {
    var detections = {};
    var finalDetection = {
      bot: false
    };
    for (var detectorName in detectors2) {
      var detector = detectors2[detectorName];
      var detectorRes = detector(components);
      var detection = { bot: false };
      if (typeof detectorRes === "string") {
        detection = { bot: true, botKind: detectorRes };
      } else if (detectorRes) {
        detection = { bot: true, botKind: BotKind.Unknown };
      }
      detections[detectorName] = detection;
      if (detection.bot) {
        finalDetection = detection;
      }
    }
    return [detections, finalDetection];
  }
  function collect(sources3) {
    return __awaiter(this, void 0, void 0, function() {
      var components, sourcesKeys;
      var _this = this;
      return __generator(this, function(_a) {
        switch (_a.label) {
          case 0:
            components = {};
            sourcesKeys = Object.keys(sources3);
            return [4, Promise.all(sourcesKeys.map(function(sourceKey) {
              return __awaiter(_this, void 0, void 0, function() {
                var res, _a2, _b, error_1;
                var _c;
                return __generator(this, function(_d) {
                  switch (_d.label) {
                    case 0:
                      res = sources3[sourceKey];
                      _d.label = 1;
                    case 1:
                      _d.trys.push([1, 3, , 4]);
                      _a2 = components;
                      _b = sourceKey;
                      _c = {};
                      return [4, res()];
                    case 2:
                      _a2[_b] = (_c.value = _d.sent(), _c.state = 0, _c);
                      return [3, 4];
                    case 3:
                      error_1 = _d.sent();
                      if (error_1 instanceof BotdError) {
                        components[sourceKey] = {
                          state: error_1.state,
                          error: "".concat(error_1.name, ": ").concat(error_1.message)
                        };
                      } else {
                        components[sourceKey] = {
                          state: -3,
                          error: error_1 instanceof Error ? "".concat(error_1.name, ": ").concat(error_1.message) : String(error_1)
                        };
                      }
                      return [3, 4];
                    case 4:
                      return [
                        2
                        /*return*/
                      ];
                  }
                });
              });
            }))];
          case 1:
            _a.sent();
            return [2, components];
        }
      });
    });
  }
  function detectAppVersion(_a) {
    var appVersion = _a.appVersion;
    if (appVersion.state !== 0)
      return false;
    if (/headless/i.test(appVersion.value))
      return BotKind.HeadlessChrome;
    if (/electron/i.test(appVersion.value))
      return BotKind.Electron;
    if (/slimerjs/i.test(appVersion.value))
      return BotKind.SlimerJS;
  }
  function arrayIncludes(arr, value) {
    return arr.indexOf(value) !== -1;
  }
  function strIncludes(str, value) {
    return str.indexOf(value) !== -1;
  }
  function arrayFind(array, callback) {
    if ("find" in array)
      return array.find(callback);
    for (var i2 = 0; i2 < array.length; i2++) {
      if (callback(array[i2], i2, array))
        return array[i2];
    }
    return void 0;
  }
  function getObjectProps(obj) {
    return Object.getOwnPropertyNames(obj);
  }
  function includes(arr) {
    var keys = [];
    for (var _i = 1; _i < arguments.length; _i++) {
      keys[_i - 1] = arguments[_i];
    }
    var _loop_1 = function(key2) {
      if (typeof key2 === "string") {
        if (arrayIncludes(arr, key2))
          return { value: true };
      } else {
        var match = arrayFind(arr, function(value) {
          return key2.test(value);
        });
        if (match != null)
          return { value: true };
      }
    };
    for (var _a = 0, keys_1 = keys; _a < keys_1.length; _a++) {
      var key = keys_1[_a];
      var state_1 = _loop_1(key);
      if (typeof state_1 === "object")
        return state_1.value;
    }
    return false;
  }
  function countTruthy(values) {
    return values.reduce(function(sum, value) {
      return sum + (value ? 1 : 0);
    }, 0);
  }
  function detectDocumentAttributes(_a) {
    var documentElementKeys = _a.documentElementKeys;
    if (documentElementKeys.state !== 0)
      return false;
    if (includes(documentElementKeys.value, "selenium", "webdriver", "driver")) {
      return BotKind.Selenium;
    }
  }
  function detectErrorTrace(_a) {
    var errorTrace = _a.errorTrace;
    if (errorTrace.state !== 0)
      return false;
    if (/PhantomJS/i.test(errorTrace.value))
      return BotKind.PhantomJS;
  }
  function detectEvalLengthInconsistency(_a) {
    var evalLength = _a.evalLength, browserKind = _a.browserKind, browserEngineKind = _a.browserEngineKind;
    if (evalLength.state !== 0 || browserKind.state !== 0 || browserEngineKind.state !== 0)
      return;
    var length = evalLength.value;
    if (browserEngineKind.value === "unknown")
      return false;
    return length === 37 && !arrayIncludes([
      "webkit",
      "gecko"
      /* BrowserEngineKind.Gecko */
    ], browserEngineKind.value) || length === 39 && !arrayIncludes([
      "internet_explorer"
      /* BrowserKind.IE */
    ], browserKind.value) || length === 33 && !arrayIncludes([
      "chromium"
      /* BrowserEngineKind.Chromium */
    ], browserEngineKind.value);
  }
  function detectFunctionBind(_a) {
    var functionBind = _a.functionBind;
    if (functionBind.state === -2)
      return BotKind.PhantomJS;
  }
  function detectLanguagesLengthInconsistency(_a) {
    var languages = _a.languages;
    if (languages.state === 0 && languages.value.length === 0) {
      return BotKind.HeadlessChrome;
    }
  }
  function detectMimeTypesConsistent(_a) {
    var mimeTypesConsistent = _a.mimeTypesConsistent;
    if (mimeTypesConsistent.state === 0 && !mimeTypesConsistent.value) {
      return BotKind.Unknown;
    }
  }
  function detectNotificationPermissions(_a) {
    var notificationPermissions = _a.notificationPermissions, browserKind = _a.browserKind;
    if (browserKind.state !== 0 || browserKind.value !== "chrome")
      return false;
    if (notificationPermissions.state === 0 && notificationPermissions.value) {
      return BotKind.HeadlessChrome;
    }
  }
  function detectPluginsArray(_a) {
    var pluginsArray = _a.pluginsArray;
    if (pluginsArray.state === 0 && !pluginsArray.value)
      return BotKind.HeadlessChrome;
  }
  function detectPluginsLengthInconsistency(_a) {
    var pluginsLength = _a.pluginsLength, android = _a.android, browserKind = _a.browserKind, browserEngineKind = _a.browserEngineKind;
    if (pluginsLength.state !== 0 || android.state !== 0 || browserKind.state !== 0 || browserEngineKind.state !== 0)
      return;
    if (browserKind.value !== "chrome" || android.value || browserEngineKind.value !== "chromium")
      return;
    if (pluginsLength.value === 0)
      return BotKind.HeadlessChrome;
  }
  function detectProcess(_a) {
    var _b;
    var process = _a.process;
    if (process.state !== 0)
      return false;
    if (process.value.type === "renderer" || ((_b = process.value.versions) === null || _b === void 0 ? void 0 : _b.electron) != null)
      return BotKind.Electron;
  }
  function detectProductSub(_a) {
    var productSub = _a.productSub, browserKind = _a.browserKind;
    if (productSub.state !== 0 || browserKind.state !== 0)
      return false;
    if ((browserKind.value === "chrome" || browserKind.value === "safari" || browserKind.value === "opera" || browserKind.value === "wechat") && productSub.value !== "20030107")
      return BotKind.Unknown;
  }
  function detectUserAgent(_a) {
    var userAgent = _a.userAgent;
    if (userAgent.state !== 0)
      return false;
    if (/PhantomJS/i.test(userAgent.value))
      return BotKind.PhantomJS;
    if (/Headless/i.test(userAgent.value))
      return BotKind.HeadlessChrome;
    if (/Electron/i.test(userAgent.value))
      return BotKind.Electron;
    if (/slimerjs/i.test(userAgent.value))
      return BotKind.SlimerJS;
  }
  function detectWebDriver(_a) {
    var webDriver = _a.webDriver;
    if (webDriver.state === 0 && webDriver.value)
      return BotKind.HeadlessChrome;
  }
  function detectWebGL(_a) {
    var webGL = _a.webGL;
    if (webGL.state === 0) {
      var _b = webGL.value, vendor = _b.vendor, renderer = _b.renderer;
      if (vendor == "Brian Paul" && renderer == "Mesa OffScreen") {
        return BotKind.HeadlessChrome;
      }
    }
  }
  function detectWindowExternal(_a) {
    var windowExternal = _a.windowExternal;
    if (windowExternal.state !== 0)
      return false;
    if (/Sequentum/i.test(windowExternal.value))
      return BotKind.Sequentum;
  }
  function detectWindowSize(_a) {
    var windowSize = _a.windowSize, documentFocus = _a.documentFocus;
    if (windowSize.state !== 0 || documentFocus.state !== 0)
      return false;
    var _b = windowSize.value, outerWidth = _b.outerWidth, outerHeight = _b.outerHeight;
    if (!documentFocus.value)
      return;
    if (outerWidth === 0 && outerHeight === 0)
      return BotKind.HeadlessChrome;
  }
  function detectDistinctiveProperties(_a) {
    var distinctiveProps = _a.distinctiveProps;
    if (distinctiveProps.state !== 0)
      return false;
    var value = distinctiveProps.value;
    var bot;
    for (bot in value)
      if (value[bot])
        return bot;
  }
  var detectors = {
    detectAppVersion,
    detectDocumentAttributes,
    detectErrorTrace,
    detectEvalLengthInconsistency,
    detectFunctionBind,
    detectLanguagesLengthInconsistency,
    detectNotificationPermissions,
    detectPluginsArray,
    detectPluginsLengthInconsistency,
    detectProcess,
    detectUserAgent,
    detectWebDriver,
    detectWebGL,
    detectWindowExternal,
    detectWindowSize,
    detectMimeTypesConsistent,
    detectProductSub,
    detectDistinctiveProperties
  };
  function getAppVersion() {
    var appVersion = navigator.appVersion;
    if (appVersion == void 0) {
      throw new BotdError(-1, "navigator.appVersion is undefined");
    }
    return appVersion;
  }
  function getDocumentElementKeys() {
    if (document.documentElement === void 0) {
      throw new BotdError(-1, "document.documentElement is undefined");
    }
    var documentElement = document.documentElement;
    if (typeof documentElement.getAttributeNames !== "function") {
      throw new BotdError(-2, "document.documentElement.getAttributeNames is not a function");
    }
    return documentElement.getAttributeNames();
  }
  function getErrorTrace() {
    try {
      null[0]();
    } catch (error) {
      if (error instanceof Error && error["stack"] != null) {
        return error.stack.toString();
      }
    }
    throw new BotdError(-3, "errorTrace signal unexpected behaviour");
  }
  function getEvalLength() {
    return eval.toString().length;
  }
  function getFunctionBind() {
    if (Function.prototype.bind === void 0) {
      throw new BotdError(-2, "Function.prototype.bind is undefined");
    }
    return Function.prototype.bind.toString();
  }
  function getBrowserEngineKind() {
    var _a, _b;
    var w = window;
    var n2 = navigator;
    if (countTruthy([
      "webkitPersistentStorage" in n2,
      "webkitTemporaryStorage" in n2,
      n2.vendor.indexOf("Google") === 0,
      "webkitResolveLocalFileSystemURL" in w,
      "BatteryManager" in w,
      "webkitMediaStream" in w,
      "webkitSpeechGrammar" in w
    ]) >= 5) {
      return "chromium";
    }
    if (countTruthy([
      "ApplePayError" in w,
      "CSSPrimitiveValue" in w,
      "Counter" in w,
      n2.vendor.indexOf("Apple") === 0,
      "getStorageUpdates" in n2,
      "WebKitMediaKeys" in w
    ]) >= 4) {
      return "webkit";
    }
    if (countTruthy([
      "buildID" in navigator,
      "MozAppearance" in ((_b = (_a = document.documentElement) === null || _a === void 0 ? void 0 : _a.style) !== null && _b !== void 0 ? _b : {}),
      "onmozfullscreenchange" in w,
      "mozInnerScreenX" in w,
      "CSSMozDocumentRule" in w,
      "CanvasCaptureMediaStream" in w
    ]) >= 4) {
      return "gecko";
    }
    return "unknown";
  }
  function getBrowserKind() {
    var _a;
    var userAgent = (_a = navigator.userAgent) === null || _a === void 0 ? void 0 : _a.toLowerCase();
    if (strIncludes(userAgent, "edg/")) {
      return "edge";
    } else if (strIncludes(userAgent, "trident") || strIncludes(userAgent, "msie")) {
      return "internet_explorer";
    } else if (strIncludes(userAgent, "wechat")) {
      return "wechat";
    } else if (strIncludes(userAgent, "firefox")) {
      return "firefox";
    } else if (strIncludes(userAgent, "opera") || strIncludes(userAgent, "opr")) {
      return "opera";
    } else if (strIncludes(userAgent, "chrome")) {
      return "chrome";
    } else if (strIncludes(userAgent, "safari")) {
      return "safari";
    } else {
      return "unknown";
    }
  }
  function isAndroid() {
    var browserEngineKind = getBrowserEngineKind();
    var isItChromium = browserEngineKind === "chromium";
    var isItGecko = browserEngineKind === "gecko";
    if (!isItChromium && !isItGecko)
      return false;
    var w = window;
    return countTruthy([
      "onorientationchange" in w,
      "orientation" in w,
      isItChromium && !("SharedWorker" in w),
      isItGecko && /android/i.test(navigator.appVersion)
    ]) >= 2;
  }
  function getDocumentFocus() {
    if (document.hasFocus === void 0) {
      return false;
    }
    return document.hasFocus();
  }
  function isChromium86OrNewer() {
    var w = window;
    return countTruthy([
      !("MediaSettingsRange" in w),
      "RTCEncodedAudioFrame" in w,
      "" + w.Intl === "[object Intl]",
      "" + w.Reflect === "[object Reflect]"
    ]) >= 3;
  }
  function getLanguages() {
    var n2 = navigator;
    var result = [];
    var language = n2.language || n2.userLanguage || n2.browserLanguage || n2.systemLanguage;
    if (language !== void 0) {
      result.push([language]);
    }
    if (Array.isArray(n2.languages)) {
      var browserEngine = getBrowserEngineKind();
      if (!(browserEngine === "chromium" && isChromium86OrNewer())) {
        result.push(n2.languages);
      }
    } else if (typeof n2.languages === "string") {
      var languages = n2.languages;
      if (languages) {
        result.push(languages.split(","));
      }
    }
    return result;
  }
  function areMimeTypesConsistent() {
    if (navigator.mimeTypes === void 0) {
      throw new BotdError(-1, "navigator.mimeTypes is undefined");
    }
    var mimeTypes = navigator.mimeTypes;
    var isConsistent = Object.getPrototypeOf(mimeTypes) === MimeTypeArray.prototype;
    for (var i2 = 0; i2 < mimeTypes.length; i2++) {
      isConsistent && (isConsistent = Object.getPrototypeOf(mimeTypes[i2]) === MimeType.prototype);
    }
    return isConsistent;
  }
  function getNotificationPermissions() {
    return __awaiter(this, void 0, void 0, function() {
      var permissions, permissionStatus;
      return __generator(this, function(_a) {
        switch (_a.label) {
          case 0:
            if (window.Notification === void 0) {
              throw new BotdError(-1, "window.Notification is undefined");
            }
            if (navigator.permissions === void 0) {
              throw new BotdError(-1, "navigator.permissions is undefined");
            }
            permissions = navigator.permissions;
            if (typeof permissions.query !== "function") {
              throw new BotdError(-2, "navigator.permissions.query is not a function");
            }
            _a.label = 1;
          case 1:
            _a.trys.push([1, 3, , 4]);
            return [4, permissions.query({ name: "notifications" })];
          case 2:
            permissionStatus = _a.sent();
            return [2, window.Notification.permission === "denied" && permissionStatus.state === "prompt"];
          case 3:
            _a.sent();
            throw new BotdError(-3, "notificationPermissions signal unexpected behaviour");
          case 4:
            return [
              2
              /*return*/
            ];
        }
      });
    });
  }
  function getPluginsArray() {
    if (navigator.plugins === void 0) {
      throw new BotdError(-1, "navigator.plugins is undefined");
    }
    if (window.PluginArray === void 0) {
      throw new BotdError(-1, "window.PluginArray is undefined");
    }
    return navigator.plugins instanceof PluginArray;
  }
  function getPluginsLength() {
    if (navigator.plugins === void 0) {
      throw new BotdError(-1, "navigator.plugins is undefined");
    }
    if (navigator.plugins.length === void 0) {
      throw new BotdError(-3, "navigator.plugins.length is undefined");
    }
    return navigator.plugins.length;
  }
  function getProcess() {
    var process = window.process;
    var errorPrefix = "window.process is";
    if (process === void 0) {
      throw new BotdError(-1, "".concat(errorPrefix, " undefined"));
    }
    if (process && typeof process !== "object") {
      throw new BotdError(-3, "".concat(errorPrefix, " not an object"));
    }
    return process;
  }
  function getProductSub() {
    var productSub = navigator.productSub;
    if (productSub === void 0) {
      throw new BotdError(-1, "navigator.productSub is undefined");
    }
    return productSub;
  }
  function getRTT() {
    if (navigator.connection === void 0) {
      throw new BotdError(-1, "navigator.connection is undefined");
    }
    if (navigator.connection.rtt === void 0) {
      throw new BotdError(-1, "navigator.connection.rtt is undefined");
    }
    return navigator.connection.rtt;
  }
  function getUserAgent() {
    return navigator.userAgent;
  }
  function getWebDriver() {
    if (navigator.webdriver == void 0) {
      throw new BotdError(-1, "navigator.webdriver is undefined");
    }
    return navigator.webdriver;
  }
  function getWebGL() {
    var canvasElement = document.createElement("canvas");
    if (typeof canvasElement.getContext !== "function") {
      throw new BotdError(-2, "HTMLCanvasElement.getContext is not a function");
    }
    var webGLContext = canvasElement.getContext("webgl");
    if (webGLContext === null) {
      throw new BotdError(-4, "WebGLRenderingContext is null");
    }
    if (typeof webGLContext.getParameter !== "function") {
      throw new BotdError(-2, "WebGLRenderingContext.getParameter is not a function");
    }
    var vendor = webGLContext.getParameter(webGLContext.VENDOR);
    var renderer = webGLContext.getParameter(webGLContext.RENDERER);
    return { vendor, renderer };
  }
  function getWindowExternal() {
    if (window.external === void 0) {
      throw new BotdError(-1, "window.external is undefined");
    }
    var external = window.external;
    if (typeof external.toString !== "function") {
      throw new BotdError(-2, "window.external.toString is not a function");
    }
    return external.toString();
  }
  function getWindowSize() {
    return {
      outerWidth: window.outerWidth,
      outerHeight: window.outerHeight,
      innerWidth: window.innerWidth,
      innerHeight: window.innerHeight
    };
  }
  function checkDistinctiveProperties() {
    var _a;
    var distinctivePropsList = (_a = {}, _a[BotKind.Awesomium] = {
      window: ["awesomium"]
    }, _a[BotKind.Cef] = {
      window: ["RunPerfTest"]
    }, _a[BotKind.CefSharp] = {
      window: ["CefSharp"]
    }, _a[BotKind.CoachJS] = {
      window: ["emit"]
    }, _a[BotKind.FMiner] = {
      window: ["fmget_targets"]
    }, _a[BotKind.Geb] = {
      window: ["geb"]
    }, _a[BotKind.NightmareJS] = {
      window: ["__nightmare", "nightmare"]
    }, _a[BotKind.Phantomas] = {
      window: ["__phantomas"]
    }, _a[BotKind.PhantomJS] = {
      window: ["callPhantom", "_phantom"]
    }, _a[BotKind.Rhino] = {
      window: ["spawn"]
    }, _a[BotKind.Selenium] = {
      window: ["_Selenium_IDE_Recorder", "_selenium", "calledSelenium", /^([a-z]){3}_.*_(Array|Promise|Symbol)$/],
      document: ["__selenium_evaluate", "selenium-evaluate", "__selenium_unwrapped"]
    }, _a[BotKind.WebDriverIO] = {
      window: ["wdioElectron"]
    }, _a[BotKind.WebDriver] = {
      window: [
        "webdriver",
        "__webdriverFunc",
        "__lastWatirAlert",
        "__lastWatirConfirm",
        "__lastWatirPrompt",
        "_WEBDRIVER_ELEM_CACHE",
        "ChromeDriverw"
      ],
      document: [
        "__webdriver_script_fn",
        "__driver_evaluate",
        "__webdriver_evaluate",
        "__fxdriver_evaluate",
        "__driver_unwrapped",
        "__webdriver_unwrapped",
        "__fxdriver_unwrapped",
        "__webdriver_script_fn",
        "__webdriver_script_func",
        "__webdriver_script_function",
        "$cdc_asdjflasutopfhvcZLmcf",
        "$cdc_asdjflasutopfhvcZLmcfl_",
        "$chrome_asyncScriptInfo",
        "__$webdriverAsyncExecutor"
      ]
    }, _a[BotKind.HeadlessChrome] = {
      window: ["domAutomation", "domAutomationController"]
    }, _a);
    var botName;
    var result = {};
    var windowProps = getObjectProps(window);
    var documentProps = [];
    if (window.document !== void 0)
      documentProps = getObjectProps(window.document);
    for (botName in distinctivePropsList) {
      var props = distinctivePropsList[botName];
      if (props !== void 0) {
        var windowContains = props.window === void 0 ? false : includes.apply(void 0, __spreadArray([windowProps], props.window, false));
        var documentContains = props.document === void 0 || !documentProps.length ? false : includes.apply(void 0, __spreadArray([documentProps], props.document, false));
        result[botName] = windowContains || documentContains;
      }
    }
    return result;
  }
  var sources = {
    android: isAndroid,
    browserKind: getBrowserKind,
    browserEngineKind: getBrowserEngineKind,
    documentFocus: getDocumentFocus,
    userAgent: getUserAgent,
    appVersion: getAppVersion,
    rtt: getRTT,
    windowSize: getWindowSize,
    pluginsLength: getPluginsLength,
    pluginsArray: getPluginsArray,
    errorTrace: getErrorTrace,
    productSub: getProductSub,
    windowExternal: getWindowExternal,
    mimeTypesConsistent: areMimeTypesConsistent,
    evalLength: getEvalLength,
    webGL: getWebGL,
    webDriver: getWebDriver,
    languages: getLanguages,
    notificationPermissions: getNotificationPermissions,
    documentElementKeys: getDocumentElementKeys,
    functionBind: getFunctionBind,
    process: getProcess,
    distinctiveProps: checkDistinctiveProperties
  };
  var BotDetector = (
    /** @class */
    function() {
      function BotDetector2() {
        this.components = void 0;
        this.detections = void 0;
      }
      BotDetector2.prototype.getComponents = function() {
        return this.components;
      };
      BotDetector2.prototype.getDetections = function() {
        return this.detections;
      };
      BotDetector2.prototype.detect = function() {
        if (this.components === void 0) {
          throw new Error("BotDetector.detect can't be called before BotDetector.collect");
        }
        var _a = detect(this.components, detectors), detections = _a[0], finalDetection = _a[1];
        this.detections = detections;
        return finalDetection;
      };
      BotDetector2.prototype.collect = function() {
        return __awaiter(this, void 0, void 0, function() {
          var _a;
          return __generator(this, function(_b) {
            switch (_b.label) {
              case 0:
                _a = this;
                return [4, collect(sources)];
              case 1:
                _a.components = _b.sent();
                return [2, this.components];
            }
          });
        });
      };
      return BotDetector2;
    }()
  );
  function monitor() {
    if (window.__fpjs_d_m || Math.random() >= 1e-3) {
      return;
    }
    try {
      var request = new XMLHttpRequest();
      request.open("get", "https://m1.openfpcdn.io/botd/v".concat(version, "/npm-monitoring"), true);
      request.send();
    } catch (error) {
      console.error(error);
    }
  }
  function load(_a) {
    var _b = _a === void 0 ? {} : _a, _c = _b.monitoring, monitoring = _c === void 0 ? true : _c;
    return __awaiter(this, void 0, void 0, function() {
      var detector;
      return __generator(this, function(_d) {
        switch (_d.label) {
          case 0:
            if (monitoring) {
              monitor();
            }
            detector = new BotDetector();
            return [4, detector.collect()];
          case 1:
            _d.sent();
            return [2, detector];
        }
      });
    });
  }

  // ../../node_modules/.pnpm/@fingerprintjs+fingerprintjs@3.4.2/node_modules/@fingerprintjs/fingerprintjs/dist/fp.esm.js
  var version2 = "3.4.2";
  function wait(durationMs, resolveWith) {
    return new Promise(function(resolve) {
      return setTimeout(resolve, durationMs, resolveWith);
    });
  }
  function requestIdleCallbackIfAvailable(fallbackTimeout, deadlineTimeout) {
    if (deadlineTimeout === void 0) {
      deadlineTimeout = Infinity;
    }
    var requestIdleCallback = window.requestIdleCallback;
    if (requestIdleCallback) {
      return new Promise(function(resolve) {
        return requestIdleCallback.call(window, function() {
          return resolve();
        }, { timeout: deadlineTimeout });
      });
    } else {
      return wait(Math.min(fallbackTimeout, deadlineTimeout));
    }
  }
  function isPromise(value) {
    return !!value && typeof value.then === "function";
  }
  function awaitIfAsync(action, callback) {
    try {
      var returnedValue = action();
      if (isPromise(returnedValue)) {
        returnedValue.then(function(result) {
          return callback(true, result);
        }, function(error) {
          return callback(false, error);
        });
      } else {
        callback(true, returnedValue);
      }
    } catch (error) {
      callback(false, error);
    }
  }
  function mapWithBreaks(items, callback, loopReleaseInterval) {
    if (loopReleaseInterval === void 0) {
      loopReleaseInterval = 16;
    }
    return __awaiter(this, void 0, void 0, function() {
      var results, lastLoopReleaseTime, i2, now;
      return __generator(this, function(_a) {
        switch (_a.label) {
          case 0:
            results = Array(items.length);
            lastLoopReleaseTime = Date.now();
            i2 = 0;
            _a.label = 1;
          case 1:
            if (!(i2 < items.length)) return [3, 4];
            results[i2] = callback(items[i2], i2);
            now = Date.now();
            if (!(now >= lastLoopReleaseTime + loopReleaseInterval)) return [3, 3];
            lastLoopReleaseTime = now;
            return [4, wait(0)];
          case 2:
            _a.sent();
            _a.label = 3;
          case 3:
            ++i2;
            return [3, 1];
          case 4:
            return [2, results];
        }
      });
    });
  }
  function suppressUnhandledRejectionWarning(promise) {
    promise.then(void 0, function() {
      return void 0;
    });
  }
  function x64Add(m, n2) {
    m = [m[0] >>> 16, m[0] & 65535, m[1] >>> 16, m[1] & 65535];
    n2 = [n2[0] >>> 16, n2[0] & 65535, n2[1] >>> 16, n2[1] & 65535];
    var o2 = [0, 0, 0, 0];
    o2[3] += m[3] + n2[3];
    o2[2] += o2[3] >>> 16;
    o2[3] &= 65535;
    o2[2] += m[2] + n2[2];
    o2[1] += o2[2] >>> 16;
    o2[2] &= 65535;
    o2[1] += m[1] + n2[1];
    o2[0] += o2[1] >>> 16;
    o2[1] &= 65535;
    o2[0] += m[0] + n2[0];
    o2[0] &= 65535;
    return [o2[0] << 16 | o2[1], o2[2] << 16 | o2[3]];
  }
  function x64Multiply(m, n2) {
    m = [m[0] >>> 16, m[0] & 65535, m[1] >>> 16, m[1] & 65535];
    n2 = [n2[0] >>> 16, n2[0] & 65535, n2[1] >>> 16, n2[1] & 65535];
    var o2 = [0, 0, 0, 0];
    o2[3] += m[3] * n2[3];
    o2[2] += o2[3] >>> 16;
    o2[3] &= 65535;
    o2[2] += m[2] * n2[3];
    o2[1] += o2[2] >>> 16;
    o2[2] &= 65535;
    o2[2] += m[3] * n2[2];
    o2[1] += o2[2] >>> 16;
    o2[2] &= 65535;
    o2[1] += m[1] * n2[3];
    o2[0] += o2[1] >>> 16;
    o2[1] &= 65535;
    o2[1] += m[2] * n2[2];
    o2[0] += o2[1] >>> 16;
    o2[1] &= 65535;
    o2[1] += m[3] * n2[1];
    o2[0] += o2[1] >>> 16;
    o2[1] &= 65535;
    o2[0] += m[0] * n2[3] + m[1] * n2[2] + m[2] * n2[1] + m[3] * n2[0];
    o2[0] &= 65535;
    return [o2[0] << 16 | o2[1], o2[2] << 16 | o2[3]];
  }
  function x64Rotl(m, n2) {
    n2 %= 64;
    if (n2 === 32) {
      return [m[1], m[0]];
    } else if (n2 < 32) {
      return [m[0] << n2 | m[1] >>> 32 - n2, m[1] << n2 | m[0] >>> 32 - n2];
    } else {
      n2 -= 32;
      return [m[1] << n2 | m[0] >>> 32 - n2, m[0] << n2 | m[1] >>> 32 - n2];
    }
  }
  function x64LeftShift(m, n2) {
    n2 %= 64;
    if (n2 === 0) {
      return m;
    } else if (n2 < 32) {
      return [m[0] << n2 | m[1] >>> 32 - n2, m[1] << n2];
    } else {
      return [m[1] << n2 - 32, 0];
    }
  }
  function x64Xor(m, n2) {
    return [m[0] ^ n2[0], m[1] ^ n2[1]];
  }
  function x64Fmix(h) {
    h = x64Xor(h, [0, h[0] >>> 1]);
    h = x64Multiply(h, [4283543511, 3981806797]);
    h = x64Xor(h, [0, h[0] >>> 1]);
    h = x64Multiply(h, [3301882366, 444984403]);
    h = x64Xor(h, [0, h[0] >>> 1]);
    return h;
  }
  function x64hash128(key, seed) {
    key = key || "";
    seed = seed || 0;
    var remainder = key.length % 16;
    var bytes = key.length - remainder;
    var h1 = [0, seed];
    var h2 = [0, seed];
    var k1 = [0, 0];
    var k2 = [0, 0];
    var c1 = [2277735313, 289559509];
    var c2 = [1291169091, 658871167];
    var i2;
    for (i2 = 0; i2 < bytes; i2 = i2 + 16) {
      k1 = [
        key.charCodeAt(i2 + 4) & 255 | (key.charCodeAt(i2 + 5) & 255) << 8 | (key.charCodeAt(i2 + 6) & 255) << 16 | (key.charCodeAt(i2 + 7) & 255) << 24,
        key.charCodeAt(i2) & 255 | (key.charCodeAt(i2 + 1) & 255) << 8 | (key.charCodeAt(i2 + 2) & 255) << 16 | (key.charCodeAt(i2 + 3) & 255) << 24
      ];
      k2 = [
        key.charCodeAt(i2 + 12) & 255 | (key.charCodeAt(i2 + 13) & 255) << 8 | (key.charCodeAt(i2 + 14) & 255) << 16 | (key.charCodeAt(i2 + 15) & 255) << 24,
        key.charCodeAt(i2 + 8) & 255 | (key.charCodeAt(i2 + 9) & 255) << 8 | (key.charCodeAt(i2 + 10) & 255) << 16 | (key.charCodeAt(i2 + 11) & 255) << 24
      ];
      k1 = x64Multiply(k1, c1);
      k1 = x64Rotl(k1, 31);
      k1 = x64Multiply(k1, c2);
      h1 = x64Xor(h1, k1);
      h1 = x64Rotl(h1, 27);
      h1 = x64Add(h1, h2);
      h1 = x64Add(x64Multiply(h1, [0, 5]), [0, 1390208809]);
      k2 = x64Multiply(k2, c2);
      k2 = x64Rotl(k2, 33);
      k2 = x64Multiply(k2, c1);
      h2 = x64Xor(h2, k2);
      h2 = x64Rotl(h2, 31);
      h2 = x64Add(h2, h1);
      h2 = x64Add(x64Multiply(h2, [0, 5]), [0, 944331445]);
    }
    k1 = [0, 0];
    k2 = [0, 0];
    switch (remainder) {
      case 15:
        k2 = x64Xor(k2, x64LeftShift([0, key.charCodeAt(i2 + 14)], 48));
      // fallthrough
      case 14:
        k2 = x64Xor(k2, x64LeftShift([0, key.charCodeAt(i2 + 13)], 40));
      // fallthrough
      case 13:
        k2 = x64Xor(k2, x64LeftShift([0, key.charCodeAt(i2 + 12)], 32));
      // fallthrough
      case 12:
        k2 = x64Xor(k2, x64LeftShift([0, key.charCodeAt(i2 + 11)], 24));
      // fallthrough
      case 11:
        k2 = x64Xor(k2, x64LeftShift([0, key.charCodeAt(i2 + 10)], 16));
      // fallthrough
      case 10:
        k2 = x64Xor(k2, x64LeftShift([0, key.charCodeAt(i2 + 9)], 8));
      // fallthrough
      case 9:
        k2 = x64Xor(k2, [0, key.charCodeAt(i2 + 8)]);
        k2 = x64Multiply(k2, c2);
        k2 = x64Rotl(k2, 33);
        k2 = x64Multiply(k2, c1);
        h2 = x64Xor(h2, k2);
      // fallthrough
      case 8:
        k1 = x64Xor(k1, x64LeftShift([0, key.charCodeAt(i2 + 7)], 56));
      // fallthrough
      case 7:
        k1 = x64Xor(k1, x64LeftShift([0, key.charCodeAt(i2 + 6)], 48));
      // fallthrough
      case 6:
        k1 = x64Xor(k1, x64LeftShift([0, key.charCodeAt(i2 + 5)], 40));
      // fallthrough
      case 5:
        k1 = x64Xor(k1, x64LeftShift([0, key.charCodeAt(i2 + 4)], 32));
      // fallthrough
      case 4:
        k1 = x64Xor(k1, x64LeftShift([0, key.charCodeAt(i2 + 3)], 24));
      // fallthrough
      case 3:
        k1 = x64Xor(k1, x64LeftShift([0, key.charCodeAt(i2 + 2)], 16));
      // fallthrough
      case 2:
        k1 = x64Xor(k1, x64LeftShift([0, key.charCodeAt(i2 + 1)], 8));
      // fallthrough
      case 1:
        k1 = x64Xor(k1, [0, key.charCodeAt(i2)]);
        k1 = x64Multiply(k1, c1);
        k1 = x64Rotl(k1, 31);
        k1 = x64Multiply(k1, c2);
        h1 = x64Xor(h1, k1);
    }
    h1 = x64Xor(h1, [0, key.length]);
    h2 = x64Xor(h2, [0, key.length]);
    h1 = x64Add(h1, h2);
    h2 = x64Add(h2, h1);
    h1 = x64Fmix(h1);
    h2 = x64Fmix(h2);
    h1 = x64Add(h1, h2);
    h2 = x64Add(h2, h1);
    return ("00000000" + (h1[0] >>> 0).toString(16)).slice(-8) + ("00000000" + (h1[1] >>> 0).toString(16)).slice(-8) + ("00000000" + (h2[0] >>> 0).toString(16)).slice(-8) + ("00000000" + (h2[1] >>> 0).toString(16)).slice(-8);
  }
  function errorToObject(error) {
    var _a;
    return __assign({ name: error.name, message: error.message, stack: (_a = error.stack) === null || _a === void 0 ? void 0 : _a.split("\n") }, error);
  }
  function includes2(haystack, needle) {
    for (var i2 = 0, l = haystack.length; i2 < l; ++i2) {
      if (haystack[i2] === needle) {
        return true;
      }
    }
    return false;
  }
  function excludes(haystack, needle) {
    return !includes2(haystack, needle);
  }
  function toInt(value) {
    return parseInt(value);
  }
  function toFloat(value) {
    return parseFloat(value);
  }
  function replaceNaN(value, replacement) {
    return typeof value === "number" && isNaN(value) ? replacement : value;
  }
  function countTruthy2(values) {
    return values.reduce(function(sum, value) {
      return sum + (value ? 1 : 0);
    }, 0);
  }
  function round(value, base) {
    if (base === void 0) {
      base = 1;
    }
    if (Math.abs(base) >= 1) {
      return Math.round(value / base) * base;
    } else {
      var counterBase = 1 / base;
      return Math.round(value * counterBase) / counterBase;
    }
  }
  function parseSimpleCssSelector(selector) {
    var _a, _b;
    var errorMessage = "Unexpected syntax '".concat(selector, "'");
    var tagMatch = /^\s*([a-z-]*)(.*)$/i.exec(selector);
    var tag = tagMatch[1] || void 0;
    var attributes = {};
    var partsRegex = /([.:#][\w-]+|\[.+?\])/gi;
    var addAttribute = function(name, value) {
      attributes[name] = attributes[name] || [];
      attributes[name].push(value);
    };
    for (; ; ) {
      var match = partsRegex.exec(tagMatch[2]);
      if (!match) {
        break;
      }
      var part = match[0];
      switch (part[0]) {
        case ".":
          addAttribute("class", part.slice(1));
          break;
        case "#":
          addAttribute("id", part.slice(1));
          break;
        case "[": {
          var attributeMatch = /^\[([\w-]+)([~|^$*]?=("(.*?)"|([\w-]+)))?(\s+[is])?\]$/.exec(part);
          if (attributeMatch) {
            addAttribute(attributeMatch[1], (_b = (_a = attributeMatch[4]) !== null && _a !== void 0 ? _a : attributeMatch[5]) !== null && _b !== void 0 ? _b : "");
          } else {
            throw new Error(errorMessage);
          }
          break;
        }
        default:
          throw new Error(errorMessage);
      }
    }
    return [tag, attributes];
  }
  function ensureErrorWithMessage(error) {
    return error && typeof error === "object" && "message" in error ? error : { message: error };
  }
  function isFinalResultLoaded(loadResult) {
    return typeof loadResult !== "function";
  }
  function loadSource(source, sourceOptions) {
    var sourceLoadPromise = new Promise(function(resolveLoad) {
      var loadStartTime = Date.now();
      awaitIfAsync(source.bind(null, sourceOptions), function() {
        var loadArgs = [];
        for (var _i = 0; _i < arguments.length; _i++) {
          loadArgs[_i] = arguments[_i];
        }
        var loadDuration = Date.now() - loadStartTime;
        if (!loadArgs[0]) {
          return resolveLoad(function() {
            return { error: ensureErrorWithMessage(loadArgs[1]), duration: loadDuration };
          });
        }
        var loadResult = loadArgs[1];
        if (isFinalResultLoaded(loadResult)) {
          return resolveLoad(function() {
            return { value: loadResult, duration: loadDuration };
          });
        }
        resolveLoad(function() {
          return new Promise(function(resolveGet) {
            var getStartTime = Date.now();
            awaitIfAsync(loadResult, function() {
              var getArgs = [];
              for (var _i2 = 0; _i2 < arguments.length; _i2++) {
                getArgs[_i2] = arguments[_i2];
              }
              var duration = loadDuration + Date.now() - getStartTime;
              if (!getArgs[0]) {
                return resolveGet({ error: ensureErrorWithMessage(getArgs[1]), duration });
              }
              resolveGet({ value: getArgs[1], duration });
            });
          });
        });
      });
    });
    suppressUnhandledRejectionWarning(sourceLoadPromise);
    return function getComponent() {
      return sourceLoadPromise.then(function(finalizeSource) {
        return finalizeSource();
      });
    };
  }
  function loadSources(sources3, sourceOptions, excludeSources) {
    var includedSources = Object.keys(sources3).filter(function(sourceKey) {
      return excludes(excludeSources, sourceKey);
    });
    var sourceGettersPromise = mapWithBreaks(includedSources, function(sourceKey) {
      return loadSource(sources3[sourceKey], sourceOptions);
    });
    suppressUnhandledRejectionWarning(sourceGettersPromise);
    return function getComponents() {
      return __awaiter(this, void 0, void 0, function() {
        var sourceGetters, componentPromises, componentArray, components, index;
        return __generator(this, function(_a) {
          switch (_a.label) {
            case 0:
              return [4, sourceGettersPromise];
            case 1:
              sourceGetters = _a.sent();
              return [4, mapWithBreaks(sourceGetters, function(sourceGetter) {
                var componentPromise = sourceGetter();
                suppressUnhandledRejectionWarning(componentPromise);
                return componentPromise;
              })];
            case 2:
              componentPromises = _a.sent();
              return [
                4,
                Promise.all(componentPromises)
                // Keeping the component keys order the same as the source keys order
              ];
            case 3:
              componentArray = _a.sent();
              components = {};
              for (index = 0; index < includedSources.length; ++index) {
                components[includedSources[index]] = componentArray[index];
              }
              return [2, components];
          }
        });
      });
    };
  }
  function isTrident() {
    var w = window;
    var n2 = navigator;
    return countTruthy2([
      "MSCSSMatrix" in w,
      "msSetImmediate" in w,
      "msIndexedDB" in w,
      "msMaxTouchPoints" in n2,
      "msPointerEnabled" in n2
    ]) >= 4;
  }
  function isEdgeHTML() {
    var w = window;
    var n2 = navigator;
    return countTruthy2(["msWriteProfilerMark" in w, "MSStream" in w, "msLaunchUri" in n2, "msSaveBlob" in n2]) >= 3 && !isTrident();
  }
  function isChromium() {
    var w = window;
    var n2 = navigator;
    return countTruthy2([
      "webkitPersistentStorage" in n2,
      "webkitTemporaryStorage" in n2,
      n2.vendor.indexOf("Google") === 0,
      "webkitResolveLocalFileSystemURL" in w,
      "BatteryManager" in w,
      "webkitMediaStream" in w,
      "webkitSpeechGrammar" in w
    ]) >= 5;
  }
  function isWebKit() {
    var w = window;
    var n2 = navigator;
    return countTruthy2([
      "ApplePayError" in w,
      "CSSPrimitiveValue" in w,
      "Counter" in w,
      n2.vendor.indexOf("Apple") === 0,
      "getStorageUpdates" in n2,
      "WebKitMediaKeys" in w
    ]) >= 4;
  }
  function isDesktopSafari() {
    var w = window;
    return countTruthy2([
      "safari" in w,
      !("DeviceMotionEvent" in w),
      !("ongestureend" in w),
      !("standalone" in navigator)
    ]) >= 3;
  }
  function isGecko() {
    var _a, _b;
    var w = window;
    return countTruthy2([
      "buildID" in navigator,
      "MozAppearance" in ((_b = (_a = document.documentElement) === null || _a === void 0 ? void 0 : _a.style) !== null && _b !== void 0 ? _b : {}),
      "onmozfullscreenchange" in w,
      "mozInnerScreenX" in w,
      "CSSMozDocumentRule" in w,
      "CanvasCaptureMediaStream" in w
    ]) >= 4;
  }
  function isChromium86OrNewer2() {
    var w = window;
    return countTruthy2([
      !("MediaSettingsRange" in w),
      "RTCEncodedAudioFrame" in w,
      "" + w.Intl === "[object Intl]",
      "" + w.Reflect === "[object Reflect]"
    ]) >= 3;
  }
  function isWebKit606OrNewer() {
    var w = window;
    return countTruthy2([
      "DOMRectList" in w,
      "RTCPeerConnectionIceEvent" in w,
      "SVGGeometryElement" in w,
      "ontransitioncancel" in w
    ]) >= 3;
  }
  function isIPad() {
    if (navigator.platform === "iPad") {
      return true;
    }
    var s = screen;
    var screenRatio = s.width / s.height;
    return countTruthy2([
      "MediaSource" in window,
      !!Element.prototype.webkitRequestFullscreen,
      // iPhone 4S that runs iOS 9 matches this. But it won't match the criteria above, so it won't be detected as iPad.
      screenRatio > 0.65 && screenRatio < 1.53
    ]) >= 2;
  }
  function getFullscreenElement() {
    var d = document;
    return d.fullscreenElement || d.msFullscreenElement || d.mozFullScreenElement || d.webkitFullscreenElement || null;
  }
  function exitFullscreen() {
    var d = document;
    return (d.exitFullscreen || d.msExitFullscreen || d.mozCancelFullScreen || d.webkitExitFullscreen).call(d);
  }
  function isAndroid2() {
    var isItChromium = isChromium();
    var isItGecko = isGecko();
    if (!isItChromium && !isItGecko) {
      return false;
    }
    var w = window;
    return countTruthy2([
      "onorientationchange" in w,
      "orientation" in w,
      isItChromium && !("SharedWorker" in w),
      isItGecko && /android/i.test(navigator.appVersion)
    ]) >= 2;
  }
  function getAudioFingerprint() {
    var w = window;
    var AudioContext = w.OfflineAudioContext || w.webkitOfflineAudioContext;
    if (!AudioContext) {
      return -2;
    }
    if (doesCurrentBrowserSuspendAudioContext()) {
      return -1;
    }
    var hashFromIndex = 4500;
    var hashToIndex = 5e3;
    var context = new AudioContext(1, hashToIndex, 44100);
    var oscillator = context.createOscillator();
    oscillator.type = "triangle";
    oscillator.frequency.value = 1e4;
    var compressor = context.createDynamicsCompressor();
    compressor.threshold.value = -50;
    compressor.knee.value = 40;
    compressor.ratio.value = 12;
    compressor.attack.value = 0;
    compressor.release.value = 0.25;
    oscillator.connect(compressor);
    compressor.connect(context.destination);
    oscillator.start(0);
    var _a = startRenderingAudio(context), renderPromise = _a[0], finishRendering = _a[1];
    var fingerprintPromise = renderPromise.then(function(buffer) {
      return getHash(buffer.getChannelData(0).subarray(hashFromIndex));
    }, function(error) {
      if (error.name === "timeout" || error.name === "suspended") {
        return -3;
      }
      throw error;
    });
    suppressUnhandledRejectionWarning(fingerprintPromise);
    return function() {
      finishRendering();
      return fingerprintPromise;
    };
  }
  function doesCurrentBrowserSuspendAudioContext() {
    return isWebKit() && !isDesktopSafari() && !isWebKit606OrNewer();
  }
  function startRenderingAudio(context) {
    var renderTryMaxCount = 3;
    var renderRetryDelay = 500;
    var runningMaxAwaitTime = 500;
    var runningSufficientTime = 5e3;
    var finalize = function() {
      return void 0;
    };
    var resultPromise = new Promise(function(resolve, reject) {
      var isFinalized = false;
      var renderTryCount = 0;
      var startedRunningAt = 0;
      context.oncomplete = function(event) {
        return resolve(event.renderedBuffer);
      };
      var startRunningTimeout = function() {
        setTimeout(function() {
          return reject(makeInnerError(
            "timeout"
            /* InnerErrorName.Timeout */
          ));
        }, Math.min(runningMaxAwaitTime, startedRunningAt + runningSufficientTime - Date.now()));
      };
      var tryRender = function() {
        try {
          var renderingPromise = context.startRendering();
          if (isPromise(renderingPromise)) {
            suppressUnhandledRejectionWarning(renderingPromise);
          }
          switch (context.state) {
            case "running":
              startedRunningAt = Date.now();
              if (isFinalized) {
                startRunningTimeout();
              }
              break;
            // Sometimes the audio context doesn't start after calling `startRendering` (in addition to the cases where
            // audio context doesn't start at all). A known case is starting an audio context when the browser tab is in
            // background on iPhone. Retries usually help in this case.
            case "suspended":
              if (!document.hidden) {
                renderTryCount++;
              }
              if (isFinalized && renderTryCount >= renderTryMaxCount) {
                reject(makeInnerError(
                  "suspended"
                  /* InnerErrorName.Suspended */
                ));
              } else {
                setTimeout(tryRender, renderRetryDelay);
              }
              break;
          }
        } catch (error) {
          reject(error);
        }
      };
      tryRender();
      finalize = function() {
        if (!isFinalized) {
          isFinalized = true;
          if (startedRunningAt > 0) {
            startRunningTimeout();
          }
        }
      };
    });
    return [resultPromise, finalize];
  }
  function getHash(signal) {
    var hash = 0;
    for (var i2 = 0; i2 < signal.length; ++i2) {
      hash += Math.abs(signal[i2]);
    }
    return hash;
  }
  function makeInnerError(name) {
    var error = new Error(name);
    error.name = name;
    return error;
  }
  function withIframe(action, initialHtml, domPollInterval) {
    var _a, _b, _c;
    if (domPollInterval === void 0) {
      domPollInterval = 50;
    }
    return __awaiter(this, void 0, void 0, function() {
      var d, iframe;
      return __generator(this, function(_d) {
        switch (_d.label) {
          case 0:
            d = document;
            _d.label = 1;
          case 1:
            if (!!d.body) return [3, 3];
            return [4, wait(domPollInterval)];
          case 2:
            _d.sent();
            return [3, 1];
          case 3:
            iframe = d.createElement("iframe");
            _d.label = 4;
          case 4:
            _d.trys.push([4, , 10, 11]);
            return [4, new Promise(function(_resolve, _reject) {
              var isComplete = false;
              var resolve = function() {
                isComplete = true;
                _resolve();
              };
              var reject = function(error) {
                isComplete = true;
                _reject(error);
              };
              iframe.onload = resolve;
              iframe.onerror = reject;
              var style = iframe.style;
              style.setProperty("display", "block", "important");
              style.position = "absolute";
              style.top = "0";
              style.left = "0";
              style.visibility = "hidden";
              if (initialHtml && "srcdoc" in iframe) {
                iframe.srcdoc = initialHtml;
              } else {
                iframe.src = "about:blank";
              }
              d.body.appendChild(iframe);
              var checkReadyState = function() {
                var _a2, _b2;
                if (isComplete) {
                  return;
                }
                if (((_b2 = (_a2 = iframe.contentWindow) === null || _a2 === void 0 ? void 0 : _a2.document) === null || _b2 === void 0 ? void 0 : _b2.readyState) === "complete") {
                  resolve();
                } else {
                  setTimeout(checkReadyState, 10);
                }
              };
              checkReadyState();
            })];
          case 5:
            _d.sent();
            _d.label = 6;
          case 6:
            if (!!((_b = (_a = iframe.contentWindow) === null || _a === void 0 ? void 0 : _a.document) === null || _b === void 0 ? void 0 : _b.body)) return [3, 8];
            return [4, wait(domPollInterval)];
          case 7:
            _d.sent();
            return [3, 6];
          case 8:
            return [4, action(iframe, iframe.contentWindow)];
          case 9:
            return [2, _d.sent()];
          case 10:
            (_c = iframe.parentNode) === null || _c === void 0 ? void 0 : _c.removeChild(iframe);
            return [
              7
              /*endfinally*/
            ];
          case 11:
            return [
              2
              /*return*/
            ];
        }
      });
    });
  }
  function selectorToElement(selector) {
    var _a = parseSimpleCssSelector(selector), tag = _a[0], attributes = _a[1];
    var element = document.createElement(tag !== null && tag !== void 0 ? tag : "div");
    for (var _i = 0, _b = Object.keys(attributes); _i < _b.length; _i++) {
      var name_1 = _b[_i];
      var value = attributes[name_1].join(" ");
      if (name_1 === "style") {
        addStyleString(element.style, value);
      } else {
        element.setAttribute(name_1, value);
      }
    }
    return element;
  }
  function addStyleString(style, source) {
    for (var _i = 0, _a = source.split(";"); _i < _a.length; _i++) {
      var property = _a[_i];
      var match = /^\s*([\w-]+)\s*:\s*(.+?)(\s*!([\w-]+))?\s*$/.exec(property);
      if (match) {
        var name_2 = match[1], value = match[2], priority = match[4];
        style.setProperty(name_2, value, priority || "");
      }
    }
  }
  var testString = "mmMwWLliI0O&1";
  var textSize = "48px";
  var baseFonts = ["monospace", "sans-serif", "serif"];
  var fontList = [
    // This is android-specific font from "Roboto" family
    "sans-serif-thin",
    "ARNO PRO",
    "Agency FB",
    "Arabic Typesetting",
    "Arial Unicode MS",
    "AvantGarde Bk BT",
    "BankGothic Md BT",
    "Batang",
    "Bitstream Vera Sans Mono",
    "Calibri",
    "Century",
    "Century Gothic",
    "Clarendon",
    "EUROSTILE",
    "Franklin Gothic",
    "Futura Bk BT",
    "Futura Md BT",
    "GOTHAM",
    "Gill Sans",
    "HELV",
    "Haettenschweiler",
    "Helvetica Neue",
    "Humanst521 BT",
    "Leelawadee",
    "Letter Gothic",
    "Levenim MT",
    "Lucida Bright",
    "Lucida Sans",
    "Menlo",
    "MS Mincho",
    "MS Outlook",
    "MS Reference Specialty",
    "MS UI Gothic",
    "MT Extra",
    "MYRIAD PRO",
    "Marlett",
    "Meiryo UI",
    "Microsoft Uighur",
    "Minion Pro",
    "Monotype Corsiva",
    "PMingLiU",
    "Pristina",
    "SCRIPTINA",
    "Segoe UI Light",
    "Serifa",
    "SimHei",
    "Small Fonts",
    "Staccato222 BT",
    "TRAJAN PRO",
    "Univers CE 55 Medium",
    "Vrinda",
    "ZWAdobeF"
  ];
  function getFonts() {
    return withIframe(function(_, _a) {
      var document2 = _a.document;
      var holder = document2.body;
      holder.style.fontSize = textSize;
      var spansContainer = document2.createElement("div");
      var defaultWidth = {};
      var defaultHeight = {};
      var createSpan = function(fontFamily) {
        var span = document2.createElement("span");
        var style = span.style;
        style.position = "absolute";
        style.top = "0";
        style.left = "0";
        style.fontFamily = fontFamily;
        span.textContent = testString;
        spansContainer.appendChild(span);
        return span;
      };
      var createSpanWithFonts = function(fontToDetect, baseFont) {
        return createSpan("'".concat(fontToDetect, "',").concat(baseFont));
      };
      var initializeBaseFontsSpans = function() {
        return baseFonts.map(createSpan);
      };
      var initializeFontsSpans = function() {
        var spans = {};
        var _loop_1 = function(font2) {
          spans[font2] = baseFonts.map(function(baseFont) {
            return createSpanWithFonts(font2, baseFont);
          });
        };
        for (var _i = 0, fontList_1 = fontList; _i < fontList_1.length; _i++) {
          var font = fontList_1[_i];
          _loop_1(font);
        }
        return spans;
      };
      var isFontAvailable = function(fontSpans) {
        return baseFonts.some(function(baseFont, baseFontIndex) {
          return fontSpans[baseFontIndex].offsetWidth !== defaultWidth[baseFont] || fontSpans[baseFontIndex].offsetHeight !== defaultHeight[baseFont];
        });
      };
      var baseFontsSpans = initializeBaseFontsSpans();
      var fontsSpans = initializeFontsSpans();
      holder.appendChild(spansContainer);
      for (var index = 0; index < baseFonts.length; index++) {
        defaultWidth[baseFonts[index]] = baseFontsSpans[index].offsetWidth;
        defaultHeight[baseFonts[index]] = baseFontsSpans[index].offsetHeight;
      }
      return fontList.filter(function(font) {
        return isFontAvailable(fontsSpans[font]);
      });
    });
  }
  function getPlugins() {
    var rawPlugins = navigator.plugins;
    if (!rawPlugins) {
      return void 0;
    }
    var plugins = [];
    for (var i2 = 0; i2 < rawPlugins.length; ++i2) {
      var plugin = rawPlugins[i2];
      if (!plugin) {
        continue;
      }
      var mimeTypes = [];
      for (var j = 0; j < plugin.length; ++j) {
        var mimeType = plugin[j];
        mimeTypes.push({
          type: mimeType.type,
          suffixes: mimeType.suffixes
        });
      }
      plugins.push({
        name: plugin.name,
        description: plugin.description,
        mimeTypes
      });
    }
    return plugins;
  }
  function getCanvasFingerprint() {
    var winding = false;
    var geometry;
    var text;
    var _a = makeCanvasContext(), canvas = _a[0], context = _a[1];
    if (!isSupported(canvas, context)) {
      geometry = text = "";
    } else {
      winding = doesSupportWinding(context);
      renderTextImage(canvas, context);
      var textImage1 = canvasToString(canvas);
      var textImage2 = canvasToString(canvas);
      if (textImage1 !== textImage2) {
        geometry = text = "unstable";
      } else {
        text = textImage1;
        renderGeometryImage(canvas, context);
        geometry = canvasToString(canvas);
      }
    }
    return { winding, geometry, text };
  }
  function makeCanvasContext() {
    var canvas = document.createElement("canvas");
    canvas.width = 1;
    canvas.height = 1;
    return [canvas, canvas.getContext("2d")];
  }
  function isSupported(canvas, context) {
    return !!(context && canvas.toDataURL);
  }
  function doesSupportWinding(context) {
    context.rect(0, 0, 10, 10);
    context.rect(2, 2, 6, 6);
    return !context.isPointInPath(5, 5, "evenodd");
  }
  function renderTextImage(canvas, context) {
    canvas.width = 240;
    canvas.height = 60;
    context.textBaseline = "alphabetic";
    context.fillStyle = "#f60";
    context.fillRect(100, 1, 62, 20);
    context.fillStyle = "#069";
    context.font = '11pt "Times New Roman"';
    var printedText = "Cwm fjordbank gly ".concat(
      String.fromCharCode(55357, 56835)
      /* 😃 */
    );
    context.fillText(printedText, 2, 15);
    context.fillStyle = "rgba(102, 204, 0, 0.2)";
    context.font = "18pt Arial";
    context.fillText(printedText, 4, 45);
  }
  function renderGeometryImage(canvas, context) {
    canvas.width = 122;
    canvas.height = 110;
    context.globalCompositeOperation = "multiply";
    for (var _i = 0, _a = [
      ["#f2f", 40, 40],
      ["#2ff", 80, 40],
      ["#ff2", 60, 80]
    ]; _i < _a.length; _i++) {
      var _b = _a[_i], color = _b[0], x = _b[1], y = _b[2];
      context.fillStyle = color;
      context.beginPath();
      context.arc(x, y, 40, 0, Math.PI * 2, true);
      context.closePath();
      context.fill();
    }
    context.fillStyle = "#f9c";
    context.arc(60, 60, 60, 0, Math.PI * 2, true);
    context.arc(60, 60, 20, 0, Math.PI * 2, true);
    context.fill("evenodd");
  }
  function canvasToString(canvas) {
    return canvas.toDataURL();
  }
  function getTouchSupport() {
    var n2 = navigator;
    var maxTouchPoints = 0;
    var touchEvent;
    if (n2.maxTouchPoints !== void 0) {
      maxTouchPoints = toInt(n2.maxTouchPoints);
    } else if (n2.msMaxTouchPoints !== void 0) {
      maxTouchPoints = n2.msMaxTouchPoints;
    }
    try {
      document.createEvent("TouchEvent");
      touchEvent = true;
    } catch (_a) {
      touchEvent = false;
    }
    var touchStart = "ontouchstart" in window;
    return {
      maxTouchPoints,
      touchEvent,
      touchStart
    };
  }
  function getOsCpu() {
    return navigator.oscpu;
  }
  function getLanguages2() {
    var n2 = navigator;
    var result = [];
    var language = n2.language || n2.userLanguage || n2.browserLanguage || n2.systemLanguage;
    if (language !== void 0) {
      result.push([language]);
    }
    if (Array.isArray(n2.languages)) {
      if (!(isChromium() && isChromium86OrNewer2())) {
        result.push(n2.languages);
      }
    } else if (typeof n2.languages === "string") {
      var languages = n2.languages;
      if (languages) {
        result.push(languages.split(","));
      }
    }
    return result;
  }
  function getColorDepth() {
    return window.screen.colorDepth;
  }
  function getDeviceMemory() {
    return replaceNaN(toFloat(navigator.deviceMemory), void 0);
  }
  function getScreenResolution() {
    var s = screen;
    var parseDimension = function(value) {
      return replaceNaN(toInt(value), null);
    };
    var dimensions = [parseDimension(s.width), parseDimension(s.height)];
    dimensions.sort().reverse();
    return dimensions;
  }
  var screenFrameCheckInterval = 2500;
  var roundingPrecision = 10;
  var screenFrameBackup;
  var screenFrameSizeTimeoutId;
  function watchScreenFrame() {
    if (screenFrameSizeTimeoutId !== void 0) {
      return;
    }
    var checkScreenFrame = function() {
      var frameSize = getCurrentScreenFrame();
      if (isFrameSizeNull(frameSize)) {
        screenFrameSizeTimeoutId = setTimeout(checkScreenFrame, screenFrameCheckInterval);
      } else {
        screenFrameBackup = frameSize;
        screenFrameSizeTimeoutId = void 0;
      }
    };
    checkScreenFrame();
  }
  function getScreenFrame() {
    var _this = this;
    watchScreenFrame();
    return function() {
      return __awaiter(_this, void 0, void 0, function() {
        var frameSize;
        return __generator(this, function(_a) {
          switch (_a.label) {
            case 0:
              frameSize = getCurrentScreenFrame();
              if (!isFrameSizeNull(frameSize)) return [3, 2];
              if (screenFrameBackup) {
                return [2, __spreadArray([], screenFrameBackup, true)];
              }
              if (!getFullscreenElement()) return [3, 2];
              return [4, exitFullscreen()];
            case 1:
              _a.sent();
              frameSize = getCurrentScreenFrame();
              _a.label = 2;
            case 2:
              if (!isFrameSizeNull(frameSize)) {
                screenFrameBackup = frameSize;
              }
              return [2, frameSize];
          }
        });
      });
    };
  }
  function getRoundedScreenFrame() {
    var _this = this;
    var screenFrameGetter = getScreenFrame();
    return function() {
      return __awaiter(_this, void 0, void 0, function() {
        var frameSize, processSize;
        return __generator(this, function(_a) {
          switch (_a.label) {
            case 0:
              return [4, screenFrameGetter()];
            case 1:
              frameSize = _a.sent();
              processSize = function(sideSize) {
                return sideSize === null ? null : round(sideSize, roundingPrecision);
              };
              return [2, [processSize(frameSize[0]), processSize(frameSize[1]), processSize(frameSize[2]), processSize(frameSize[3])]];
          }
        });
      });
    };
  }
  function getCurrentScreenFrame() {
    var s = screen;
    return [
      replaceNaN(toFloat(s.availTop), null),
      replaceNaN(toFloat(s.width) - toFloat(s.availWidth) - replaceNaN(toFloat(s.availLeft), 0), null),
      replaceNaN(toFloat(s.height) - toFloat(s.availHeight) - replaceNaN(toFloat(s.availTop), 0), null),
      replaceNaN(toFloat(s.availLeft), null)
    ];
  }
  function isFrameSizeNull(frameSize) {
    for (var i2 = 0; i2 < 4; ++i2) {
      if (frameSize[i2]) {
        return false;
      }
    }
    return true;
  }
  function getHardwareConcurrency() {
    return replaceNaN(toInt(navigator.hardwareConcurrency), void 0);
  }
  function getTimezone() {
    var _a;
    var DateTimeFormat = (_a = window.Intl) === null || _a === void 0 ? void 0 : _a.DateTimeFormat;
    if (DateTimeFormat) {
      var timezone = new DateTimeFormat().resolvedOptions().timeZone;
      if (timezone) {
        return timezone;
      }
    }
    var offset = -getTimezoneOffset();
    return "UTC".concat(offset >= 0 ? "+" : "").concat(Math.abs(offset));
  }
  function getTimezoneOffset() {
    var currentYear = (/* @__PURE__ */ new Date()).getFullYear();
    return Math.max(
      // `getTimezoneOffset` returns a number as a string in some unidentified cases
      toFloat(new Date(currentYear, 0, 1).getTimezoneOffset()),
      toFloat(new Date(currentYear, 6, 1).getTimezoneOffset())
    );
  }
  function getSessionStorage() {
    try {
      return !!window.sessionStorage;
    } catch (error) {
      return true;
    }
  }
  function getLocalStorage() {
    try {
      return !!window.localStorage;
    } catch (e2) {
      return true;
    }
  }
  function getIndexedDB() {
    if (isTrident() || isEdgeHTML()) {
      return void 0;
    }
    try {
      return !!window.indexedDB;
    } catch (e2) {
      return true;
    }
  }
  function getOpenDatabase() {
    return !!window.openDatabase;
  }
  function getCpuClass() {
    return navigator.cpuClass;
  }
  function getPlatform() {
    var platform = navigator.platform;
    if (platform === "MacIntel") {
      if (isWebKit() && !isDesktopSafari()) {
        return isIPad() ? "iPad" : "iPhone";
      }
    }
    return platform;
  }
  function getVendor() {
    return navigator.vendor || "";
  }
  function getVendorFlavors() {
    var flavors = [];
    for (var _i = 0, _a = [
      // Blink and some browsers on iOS
      "chrome",
      // Safari on macOS
      "safari",
      // Chrome on iOS (checked in 85 on 13 and 87 on 14)
      "__crWeb",
      "__gCrWeb",
      // Yandex Browser on iOS, macOS and Android (checked in 21.2 on iOS 14, macOS and Android)
      "yandex",
      // Yandex Browser on iOS (checked in 21.2 on 14)
      "__yb",
      "__ybro",
      // Firefox on iOS (checked in 32 on 14)
      "__firefox__",
      // Edge on iOS (checked in 46 on 14)
      "__edgeTrackingPreventionStatistics",
      "webkit",
      // Opera Touch on iOS (checked in 2.6 on 14)
      "oprt",
      // Samsung Internet on Android (checked in 11.1)
      "samsungAr",
      // UC Browser on Android (checked in 12.10 and 13.0)
      "ucweb",
      "UCShellJava",
      // Puffin on Android (checked in 9.0)
      "puffinDevice"
      // UC on iOS and Opera on Android have no specific global variables
      // Edge for Android isn't checked
    ]; _i < _a.length; _i++) {
      var key = _a[_i];
      var value = window[key];
      if (value && typeof value === "object") {
        flavors.push(key);
      }
    }
    return flavors.sort();
  }
  function areCookiesEnabled() {
    var d = document;
    try {
      d.cookie = "cookietest=1; SameSite=Strict;";
      var result = d.cookie.indexOf("cookietest=") !== -1;
      d.cookie = "cookietest=1; SameSite=Strict; expires=Thu, 01-Jan-1970 00:00:01 GMT";
      return result;
    } catch (e2) {
      return false;
    }
  }
  function getFilters() {
    var fromB64 = atob;
    return {
      abpIndo: [
        "#Iklan-Melayang",
        "#Kolom-Iklan-728",
        "#SidebarIklan-wrapper",
        '[title="ALIENBOLA" i]',
        fromB64("I0JveC1CYW5uZXItYWRz")
      ],
      abpvn: [".quangcao", "#mobileCatfish", fromB64("LmNsb3NlLWFkcw=="), '[id^="bn_bottom_fixed_"]', "#pmadv"],
      adBlockFinland: [
        ".mainostila",
        fromB64("LnNwb25zb3JpdA=="),
        ".ylamainos",
        fromB64("YVtocmVmKj0iL2NsaWNrdGhyZ2guYXNwPyJd"),
        fromB64("YVtocmVmXj0iaHR0cHM6Ly9hcHAucmVhZHBlYWsuY29tL2FkcyJd")
      ],
      adBlockPersian: [
        "#navbar_notice_50",
        ".kadr",
        'TABLE[width="140px"]',
        "#divAgahi",
        fromB64("YVtocmVmXj0iaHR0cDovL2cxLnYuZndtcm0ubmV0L2FkLyJd")
      ],
      adBlockWarningRemoval: [
        "#adblock-honeypot",
        ".adblocker-root",
        ".wp_adblock_detect",
        fromB64("LmhlYWRlci1ibG9ja2VkLWFk"),
        fromB64("I2FkX2Jsb2NrZXI=")
      ],
      adGuardAnnoyances: [
        ".hs-sosyal",
        "#cookieconsentdiv",
        'div[class^="app_gdpr"]',
        ".as-oil",
        '[data-cypress="soft-push-notification-modal"]'
      ],
      adGuardBase: [
        ".BetterJsPopOverlay",
        fromB64("I2FkXzMwMFgyNTA="),
        fromB64("I2Jhbm5lcmZsb2F0MjI="),
        fromB64("I2NhbXBhaWduLWJhbm5lcg=="),
        fromB64("I0FkLUNvbnRlbnQ=")
      ],
      adGuardChinese: [
        fromB64("LlppX2FkX2FfSA=="),
        fromB64("YVtocmVmKj0iLmh0aGJldDM0LmNvbSJd"),
        "#widget-quan",
        fromB64("YVtocmVmKj0iLzg0OTkyMDIwLnh5eiJd"),
        fromB64("YVtocmVmKj0iLjE5NTZobC5jb20vIl0=")
      ],
      adGuardFrench: [
        "#pavePub",
        fromB64("LmFkLWRlc2t0b3AtcmVjdGFuZ2xl"),
        ".mobile_adhesion",
        ".widgetadv",
        fromB64("LmFkc19iYW4=")
      ],
      adGuardGerman: ['aside[data-portal-id="leaderboard"]'],
      adGuardJapanese: [
        "#kauli_yad_1",
        fromB64("YVtocmVmXj0iaHR0cDovL2FkMi50cmFmZmljZ2F0ZS5uZXQvIl0="),
        fromB64("Ll9wb3BJbl9pbmZpbml0ZV9hZA=="),
        fromB64("LmFkZ29vZ2xl"),
        fromB64("Ll9faXNib29zdFJldHVybkFk")
      ],
      adGuardMobile: [
        fromB64("YW1wLWF1dG8tYWRz"),
        fromB64("LmFtcF9hZA=="),
        'amp-embed[type="24smi"]',
        "#mgid_iframe1",
        fromB64("I2FkX2ludmlld19hcmVh")
      ],
      adGuardRussian: [
        fromB64("YVtocmVmXj0iaHR0cHM6Ly9hZC5sZXRtZWFkcy5jb20vIl0="),
        fromB64("LnJlY2xhbWE="),
        'div[id^="smi2adblock"]',
        fromB64("ZGl2W2lkXj0iQWRGb3hfYmFubmVyXyJd"),
        "#psyduckpockeball"
      ],
      adGuardSocial: [
        fromB64("YVtocmVmXj0iLy93d3cuc3R1bWJsZXVwb24uY29tL3N1Ym1pdD91cmw9Il0="),
        fromB64("YVtocmVmXj0iLy90ZWxlZ3JhbS5tZS9zaGFyZS91cmw/Il0="),
        ".etsy-tweet",
        "#inlineShare",
        ".popup-social"
      ],
      adGuardSpanishPortuguese: ["#barraPublicidade", "#Publicidade", "#publiEspecial", "#queTooltip", ".cnt-publi"],
      adGuardTrackingProtection: [
        "#qoo-counter",
        fromB64("YVtocmVmXj0iaHR0cDovL2NsaWNrLmhvdGxvZy5ydS8iXQ=="),
        fromB64("YVtocmVmXj0iaHR0cDovL2hpdGNvdW50ZXIucnUvdG9wL3N0YXQucGhwIl0="),
        fromB64("YVtocmVmXj0iaHR0cDovL3RvcC5tYWlsLnJ1L2p1bXAiXQ=="),
        "#top100counter"
      ],
      adGuardTurkish: [
        "#backkapat",
        fromB64("I3Jla2xhbWk="),
        fromB64("YVtocmVmXj0iaHR0cDovL2Fkc2Vydi5vbnRlay5jb20udHIvIl0="),
        fromB64("YVtocmVmXj0iaHR0cDovL2l6bGVuemkuY29tL2NhbXBhaWduLyJd"),
        fromB64("YVtocmVmXj0iaHR0cDovL3d3dy5pbnN0YWxsYWRzLm5ldC8iXQ==")
      ],
      bulgarian: [fromB64("dGQjZnJlZW5ldF90YWJsZV9hZHM="), "#ea_intext_div", ".lapni-pop-over", "#xenium_hot_offers"],
      easyList: [
        ".yb-floorad",
        fromB64("LndpZGdldF9wb19hZHNfd2lkZ2V0"),
        fromB64("LnRyYWZmaWNqdW5reS1hZA=="),
        ".textad_headline",
        fromB64("LnNwb25zb3JlZC10ZXh0LWxpbmtz")
      ],
      easyListChina: [
        fromB64("LmFwcGd1aWRlLXdyYXBbb25jbGljayo9ImJjZWJvcy5jb20iXQ=="),
        fromB64("LmZyb250cGFnZUFkdk0="),
        "#taotaole",
        "#aafoot.top_box",
        ".cfa_popup"
      ],
      easyListCookie: [
        ".ezmob-footer",
        ".cc-CookieWarning",
        "[data-cookie-number]",
        fromB64("LmF3LWNvb2tpZS1iYW5uZXI="),
        ".sygnal24-gdpr-modal-wrap"
      ],
      easyListCzechSlovak: [
        "#onlajny-stickers",
        fromB64("I3Jla2xhbW5pLWJveA=="),
        fromB64("LnJla2xhbWEtbWVnYWJvYXJk"),
        ".sklik",
        fromB64("W2lkXj0ic2tsaWtSZWtsYW1hIl0=")
      ],
      easyListDutch: [
        fromB64("I2FkdmVydGVudGll"),
        fromB64("I3ZpcEFkbWFya3RCYW5uZXJCbG9jaw=="),
        ".adstekst",
        fromB64("YVtocmVmXj0iaHR0cHM6Ly94bHR1YmUubmwvY2xpY2svIl0="),
        "#semilo-lrectangle"
      ],
      easyListGermany: [
        "#SSpotIMPopSlider",
        fromB64("LnNwb25zb3JsaW5rZ3J1ZW4="),
        fromB64("I3dlcmJ1bmdza3k="),
        fromB64("I3Jla2xhbWUtcmVjaHRzLW1pdHRl"),
        fromB64("YVtocmVmXj0iaHR0cHM6Ly9iZDc0Mi5jb20vIl0=")
      ],
      easyListItaly: [
        fromB64("LmJveF9hZHZfYW5udW5jaQ=="),
        ".sb-box-pubbliredazionale",
        fromB64("YVtocmVmXj0iaHR0cDovL2FmZmlsaWF6aW9uaWFkcy5zbmFpLml0LyJd"),
        fromB64("YVtocmVmXj0iaHR0cHM6Ly9hZHNlcnZlci5odG1sLml0LyJd"),
        fromB64("YVtocmVmXj0iaHR0cHM6Ly9hZmZpbGlhemlvbmlhZHMuc25haS5pdC8iXQ==")
      ],
      easyListLithuania: [
        fromB64("LnJla2xhbW9zX3RhcnBhcw=="),
        fromB64("LnJla2xhbW9zX251b3JvZG9z"),
        fromB64("aW1nW2FsdD0iUmVrbGFtaW5pcyBza3lkZWxpcyJd"),
        fromB64("aW1nW2FsdD0iRGVkaWt1b3RpLmx0IHNlcnZlcmlhaSJd"),
        fromB64("aW1nW2FsdD0iSG9zdGluZ2FzIFNlcnZlcmlhaS5sdCJd")
      ],
      estonian: [fromB64("QVtocmVmKj0iaHR0cDovL3BheTRyZXN1bHRzMjQuZXUiXQ==")],
      fanboyAnnoyances: ["#ac-lre-player", ".navigate-to-top", "#subscribe_popup", ".newsletter_holder", "#back-top"],
      fanboyAntiFacebook: [".util-bar-module-firefly-visible"],
      fanboyEnhancedTrackers: [
        ".open.pushModal",
        "#issuem-leaky-paywall-articles-zero-remaining-nag",
        "#sovrn_container",
        'div[class$="-hide"][zoompage-fontsize][style="display: block;"]',
        ".BlockNag__Card"
      ],
      fanboySocial: ["#FollowUs", "#meteored_share", "#social_follow", ".article-sharer", ".community__social-desc"],
      frellwitSwedish: [
        fromB64("YVtocmVmKj0iY2FzaW5vcHJvLnNlIl1bdGFyZ2V0PSJfYmxhbmsiXQ=="),
        fromB64("YVtocmVmKj0iZG9rdG9yLXNlLm9uZWxpbmsubWUiXQ=="),
        "article.category-samarbete",
        fromB64("ZGl2LmhvbGlkQWRz"),
        "ul.adsmodern"
      ],
      greekAdBlock: [
        fromB64("QVtocmVmKj0iYWRtYW4ub3RlbmV0LmdyL2NsaWNrPyJd"),
        fromB64("QVtocmVmKj0iaHR0cDovL2F4aWFiYW5uZXJzLmV4b2R1cy5nci8iXQ=="),
        fromB64("QVtocmVmKj0iaHR0cDovL2ludGVyYWN0aXZlLmZvcnRobmV0LmdyL2NsaWNrPyJd"),
        "DIV.agores300",
        "TABLE.advright"
      ],
      hungarian: [
        "#cemp_doboz",
        ".optimonk-iframe-container",
        fromB64("LmFkX19tYWlu"),
        fromB64("W2NsYXNzKj0iR29vZ2xlQWRzIl0="),
        "#hirdetesek_box"
      ],
      iDontCareAboutCookies: [
        '.alert-info[data-block-track*="CookieNotice"]',
        ".ModuleTemplateCookieIndicator",
        ".o--cookies--container",
        "#cookies-policy-sticky",
        "#stickyCookieBar"
      ],
      icelandicAbp: [fromB64("QVtocmVmXj0iL2ZyYW1ld29yay9yZXNvdXJjZXMvZm9ybXMvYWRzLmFzcHgiXQ==")],
      latvian: [
        fromB64("YVtocmVmPSJodHRwOi8vd3d3LnNhbGlkemluaS5sdi8iXVtzdHlsZT0iZGlzcGxheTogYmxvY2s7IHdpZHRoOiAxMjBweDsgaGVpZ2h0OiA0MHB4OyBvdmVyZmxvdzogaGlkZGVuOyBwb3NpdGlvbjogcmVsYXRpdmU7Il0="),
        fromB64("YVtocmVmPSJodHRwOi8vd3d3LnNhbGlkemluaS5sdi8iXVtzdHlsZT0iZGlzcGxheTogYmxvY2s7IHdpZHRoOiA4OHB4OyBoZWlnaHQ6IDMxcHg7IG92ZXJmbG93OiBoaWRkZW47IHBvc2l0aW9uOiByZWxhdGl2ZTsiXQ==")
      ],
      listKr: [
        fromB64("YVtocmVmKj0iLy9hZC5wbGFuYnBsdXMuY28ua3IvIl0="),
        fromB64("I2xpdmVyZUFkV3JhcHBlcg=="),
        fromB64("YVtocmVmKj0iLy9hZHYuaW1hZHJlcC5jby5rci8iXQ=="),
        fromB64("aW5zLmZhc3R2aWV3LWFk"),
        ".revenue_unit_item.dable"
      ],
      listeAr: [
        fromB64("LmdlbWluaUxCMUFk"),
        ".right-and-left-sponsers",
        fromB64("YVtocmVmKj0iLmFmbGFtLmluZm8iXQ=="),
        fromB64("YVtocmVmKj0iYm9vcmFxLm9yZyJd"),
        fromB64("YVtocmVmKj0iZHViaXp6bGUuY29tL2FyLz91dG1fc291cmNlPSJd")
      ],
      listeFr: [
        fromB64("YVtocmVmXj0iaHR0cDovL3Byb21vLnZhZG9yLmNvbS8iXQ=="),
        fromB64("I2FkY29udGFpbmVyX3JlY2hlcmNoZQ=="),
        fromB64("YVtocmVmKj0id2Vib3JhbWEuZnIvZmNnaS1iaW4vIl0="),
        ".site-pub-interstitiel",
        'div[id^="crt-"][data-criteo-id]'
      ],
      officialPolish: [
        "#ceneo-placeholder-ceneo-12",
        fromB64("W2hyZWZePSJodHRwczovL2FmZi5zZW5kaHViLnBsLyJd"),
        fromB64("YVtocmVmXj0iaHR0cDovL2Fkdm1hbmFnZXIudGVjaGZ1bi5wbC9yZWRpcmVjdC8iXQ=="),
        fromB64("YVtocmVmXj0iaHR0cDovL3d3dy50cml6ZXIucGwvP3V0bV9zb3VyY2UiXQ=="),
        fromB64("ZGl2I3NrYXBpZWNfYWQ=")
      ],
      ro: [
        fromB64("YVtocmVmXj0iLy9hZmZ0cmsuYWx0ZXgucm8vQ291bnRlci9DbGljayJd"),
        fromB64("YVtocmVmXj0iaHR0cHM6Ly9ibGFja2ZyaWRheXNhbGVzLnJvL3Ryay9zaG9wLyJd"),
        fromB64("YVtocmVmXj0iaHR0cHM6Ly9ldmVudC4ycGVyZm9ybWFudC5jb20vZXZlbnRzL2NsaWNrIl0="),
        fromB64("YVtocmVmXj0iaHR0cHM6Ly9sLnByb2ZpdHNoYXJlLnJvLyJd"),
        'a[href^="/url/"]'
      ],
      ruAd: [
        fromB64("YVtocmVmKj0iLy9mZWJyYXJlLnJ1LyJd"),
        fromB64("YVtocmVmKj0iLy91dGltZy5ydS8iXQ=="),
        fromB64("YVtocmVmKj0iOi8vY2hpa2lkaWtpLnJ1Il0="),
        "#pgeldiz",
        ".yandex-rtb-block"
      ],
      thaiAds: [
        "a[href*=macau-uta-popup]",
        fromB64("I2Fkcy1nb29nbGUtbWlkZGxlX3JlY3RhbmdsZS1ncm91cA=="),
        fromB64("LmFkczMwMHM="),
        ".bumq",
        ".img-kosana"
      ],
      webAnnoyancesUltralist: [
        "#mod-social-share-2",
        "#social-tools",
        fromB64("LmN0cGwtZnVsbGJhbm5lcg=="),
        ".zergnet-recommend",
        ".yt.btn-link.btn-md.btn"
      ]
    };
  }
  function getDomBlockers(_a) {
    var _b = _a === void 0 ? {} : _a, debug = _b.debug;
    return __awaiter(this, void 0, void 0, function() {
      var filters, filterNames, allSelectors, blockedSelectors, activeBlockers;
      var _c;
      return __generator(this, function(_d) {
        switch (_d.label) {
          case 0:
            if (!isApplicable()) {
              return [2, void 0];
            }
            filters = getFilters();
            filterNames = Object.keys(filters);
            allSelectors = (_c = []).concat.apply(_c, filterNames.map(function(filterName) {
              return filters[filterName];
            }));
            return [4, getBlockedSelectors(allSelectors)];
          case 1:
            blockedSelectors = _d.sent();
            if (debug) {
              printDebug(filters, blockedSelectors);
            }
            activeBlockers = filterNames.filter(function(filterName) {
              var selectors = filters[filterName];
              var blockedCount = countTruthy2(selectors.map(function(selector) {
                return blockedSelectors[selector];
              }));
              return blockedCount > selectors.length * 0.6;
            });
            activeBlockers.sort();
            return [2, activeBlockers];
        }
      });
    });
  }
  function isApplicable() {
    return isWebKit() || isAndroid2();
  }
  function getBlockedSelectors(selectors) {
    var _a;
    return __awaiter(this, void 0, void 0, function() {
      var d, root, elements, blockedSelectors, i2, element, holder, i2;
      return __generator(this, function(_b) {
        switch (_b.label) {
          case 0:
            d = document;
            root = d.createElement("div");
            elements = new Array(selectors.length);
            blockedSelectors = {};
            forceShow(root);
            for (i2 = 0; i2 < selectors.length; ++i2) {
              element = selectorToElement(selectors[i2]);
              if (element.tagName === "DIALOG") {
                element.show();
              }
              holder = d.createElement("div");
              forceShow(holder);
              holder.appendChild(element);
              root.appendChild(holder);
              elements[i2] = element;
            }
            _b.label = 1;
          case 1:
            if (!!d.body) return [3, 3];
            return [4, wait(50)];
          case 2:
            _b.sent();
            return [3, 1];
          case 3:
            d.body.appendChild(root);
            try {
              for (i2 = 0; i2 < selectors.length; ++i2) {
                if (!elements[i2].offsetParent) {
                  blockedSelectors[selectors[i2]] = true;
                }
              }
            } finally {
              (_a = root.parentNode) === null || _a === void 0 ? void 0 : _a.removeChild(root);
            }
            return [2, blockedSelectors];
        }
      });
    });
  }
  function forceShow(element) {
    element.style.setProperty("display", "block", "important");
  }
  function printDebug(filters, blockedSelectors) {
    var message = "DOM blockers debug:\n```";
    for (var _i = 0, _a = Object.keys(filters); _i < _a.length; _i++) {
      var filterName = _a[_i];
      message += "\n".concat(filterName, ":");
      for (var _b = 0, _c = filters[filterName]; _b < _c.length; _b++) {
        var selector = _c[_b];
        message += "\n  ".concat(blockedSelectors[selector] ? "\u{1F6AB}" : "\u27A1\uFE0F", " ").concat(selector);
      }
    }
    console.log("".concat(message, "\n```"));
  }
  function getColorGamut() {
    for (var _i = 0, _a = ["rec2020", "p3", "srgb"]; _i < _a.length; _i++) {
      var gamut = _a[_i];
      if (matchMedia("(color-gamut: ".concat(gamut, ")")).matches) {
        return gamut;
      }
    }
    return void 0;
  }
  function areColorsInverted() {
    if (doesMatch$4("inverted")) {
      return true;
    }
    if (doesMatch$4("none")) {
      return false;
    }
    return void 0;
  }
  function doesMatch$4(value) {
    return matchMedia("(inverted-colors: ".concat(value, ")")).matches;
  }
  function areColorsForced() {
    if (doesMatch$3("active")) {
      return true;
    }
    if (doesMatch$3("none")) {
      return false;
    }
    return void 0;
  }
  function doesMatch$3(value) {
    return matchMedia("(forced-colors: ".concat(value, ")")).matches;
  }
  var maxValueToCheck = 100;
  function getMonochromeDepth() {
    if (!matchMedia("(min-monochrome: 0)").matches) {
      return void 0;
    }
    for (var i2 = 0; i2 <= maxValueToCheck; ++i2) {
      if (matchMedia("(max-monochrome: ".concat(i2, ")")).matches) {
        return i2;
      }
    }
    throw new Error("Too high value");
  }
  function getContrastPreference() {
    if (doesMatch$2("no-preference")) {
      return 0;
    }
    if (doesMatch$2("high") || doesMatch$2("more")) {
      return 1;
    }
    if (doesMatch$2("low") || doesMatch$2("less")) {
      return -1;
    }
    if (doesMatch$2("forced")) {
      return 10;
    }
    return void 0;
  }
  function doesMatch$2(value) {
    return matchMedia("(prefers-contrast: ".concat(value, ")")).matches;
  }
  function isMotionReduced() {
    if (doesMatch$1("reduce")) {
      return true;
    }
    if (doesMatch$1("no-preference")) {
      return false;
    }
    return void 0;
  }
  function doesMatch$1(value) {
    return matchMedia("(prefers-reduced-motion: ".concat(value, ")")).matches;
  }
  function isHDR() {
    if (doesMatch("high")) {
      return true;
    }
    if (doesMatch("standard")) {
      return false;
    }
    return void 0;
  }
  function doesMatch(value) {
    return matchMedia("(dynamic-range: ".concat(value, ")")).matches;
  }
  var M = Math;
  var fallbackFn = function() {
    return 0;
  };
  function getMathFingerprint() {
    var acos = M.acos || fallbackFn;
    var acosh = M.acosh || fallbackFn;
    var asin = M.asin || fallbackFn;
    var asinh = M.asinh || fallbackFn;
    var atanh = M.atanh || fallbackFn;
    var atan = M.atan || fallbackFn;
    var sin = M.sin || fallbackFn;
    var sinh = M.sinh || fallbackFn;
    var cos = M.cos || fallbackFn;
    var cosh = M.cosh || fallbackFn;
    var tan = M.tan || fallbackFn;
    var tanh = M.tanh || fallbackFn;
    var exp = M.exp || fallbackFn;
    var expm1 = M.expm1 || fallbackFn;
    var log1p = M.log1p || fallbackFn;
    var powPI = function(value) {
      return M.pow(M.PI, value);
    };
    var acoshPf = function(value) {
      return M.log(value + M.sqrt(value * value - 1));
    };
    var asinhPf = function(value) {
      return M.log(value + M.sqrt(value * value + 1));
    };
    var atanhPf = function(value) {
      return M.log((1 + value) / (1 - value)) / 2;
    };
    var sinhPf = function(value) {
      return M.exp(value) - 1 / M.exp(value) / 2;
    };
    var coshPf = function(value) {
      return (M.exp(value) + 1 / M.exp(value)) / 2;
    };
    var expm1Pf = function(value) {
      return M.exp(value) - 1;
    };
    var tanhPf = function(value) {
      return (M.exp(2 * value) - 1) / (M.exp(2 * value) + 1);
    };
    var log1pPf = function(value) {
      return M.log(1 + value);
    };
    return {
      acos: acos(0.12312423423423424),
      acosh: acosh(1e308),
      acoshPf: acoshPf(1e154),
      asin: asin(0.12312423423423424),
      asinh: asinh(1),
      asinhPf: asinhPf(1),
      atanh: atanh(0.5),
      atanhPf: atanhPf(0.5),
      atan: atan(0.5),
      sin: sin(-1e300),
      sinh: sinh(1),
      sinhPf: sinhPf(1),
      cos: cos(10.000000000123),
      cosh: cosh(1),
      coshPf: coshPf(1),
      tan: tan(-1e300),
      tanh: tanh(1),
      tanhPf: tanhPf(1),
      exp: exp(1),
      expm1: expm1(1),
      expm1Pf: expm1Pf(1),
      log1p: log1p(10),
      log1pPf: log1pPf(10),
      powPI: powPI(-100)
    };
  }
  var defaultText = "mmMwWLliI0fiflO&1";
  var presets = {
    /**
     * The default font. User can change it in desktop Chrome, desktop Firefox, IE 11,
     * Android Chrome (but only when the size is ≥ than the default) and Android Firefox.
     */
    default: [],
    /** OS font on macOS. User can change its size and weight. Applies after Safari restart. */
    apple: [{ font: "-apple-system-body" }],
    /** User can change it in desktop Chrome and desktop Firefox. */
    serif: [{ fontFamily: "serif" }],
    /** User can change it in desktop Chrome and desktop Firefox. */
    sans: [{ fontFamily: "sans-serif" }],
    /** User can change it in desktop Chrome and desktop Firefox. */
    mono: [{ fontFamily: "monospace" }],
    /**
     * Check the smallest allowed font size. User can change it in desktop Chrome, desktop Firefox and desktop Safari.
     * The height can be 0 in Chrome on a retina display.
     */
    min: [{ fontSize: "1px" }],
    /** Tells one OS from another in desktop Chrome. */
    system: [{ fontFamily: "system-ui" }]
  };
  function getFontPreferences() {
    return withNaturalFonts(function(document2, container) {
      var elements = {};
      var sizes = {};
      for (var _i = 0, _a = Object.keys(presets); _i < _a.length; _i++) {
        var key = _a[_i];
        var _b = presets[key], _c = _b[0], style = _c === void 0 ? {} : _c, _d = _b[1], text = _d === void 0 ? defaultText : _d;
        var element = document2.createElement("span");
        element.textContent = text;
        element.style.whiteSpace = "nowrap";
        for (var _e = 0, _f = Object.keys(style); _e < _f.length; _e++) {
          var name_1 = _f[_e];
          var value = style[name_1];
          if (value !== void 0) {
            element.style[name_1] = value;
          }
        }
        elements[key] = element;
        container.appendChild(document2.createElement("br"));
        container.appendChild(element);
      }
      for (var _g = 0, _h = Object.keys(presets); _g < _h.length; _g++) {
        var key = _h[_g];
        sizes[key] = elements[key].getBoundingClientRect().width;
      }
      return sizes;
    });
  }
  function withNaturalFonts(action, containerWidthPx) {
    if (containerWidthPx === void 0) {
      containerWidthPx = 4e3;
    }
    return withIframe(function(_, iframeWindow) {
      var iframeDocument = iframeWindow.document;
      var iframeBody = iframeDocument.body;
      var bodyStyle = iframeBody.style;
      bodyStyle.width = "".concat(containerWidthPx, "px");
      bodyStyle.webkitTextSizeAdjust = bodyStyle.textSizeAdjust = "none";
      if (isChromium()) {
        iframeBody.style.zoom = "".concat(1 / iframeWindow.devicePixelRatio);
      } else if (isWebKit()) {
        iframeBody.style.zoom = "reset";
      }
      var linesOfText = iframeDocument.createElement("div");
      linesOfText.textContent = __spreadArray([], Array(containerWidthPx / 20 << 0), true).map(function() {
        return "word";
      }).join(" ");
      iframeBody.appendChild(linesOfText);
      return action(iframeDocument, iframeBody);
    }, '<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">');
  }
  function getVideoCard() {
    var _a;
    var canvas = document.createElement("canvas");
    var gl = (_a = canvas.getContext("webgl")) !== null && _a !== void 0 ? _a : canvas.getContext("experimental-webgl");
    if (gl && "getExtension" in gl) {
      var debugInfo = gl.getExtension("WEBGL_debug_renderer_info");
      if (debugInfo) {
        return {
          vendor: (gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) || "").toString(),
          renderer: (gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) || "").toString()
        };
      }
    }
    return void 0;
  }
  function isPdfViewerEnabled() {
    return navigator.pdfViewerEnabled;
  }
  function getArchitecture() {
    var f = new Float32Array(1);
    var u8 = new Uint8Array(f.buffer);
    f[0] = Infinity;
    f[0] = f[0] - f[0];
    return u8[3];
  }
  var sources2 = {
    // READ FIRST:
    // See https://github.com/fingerprintjs/fingerprintjs/blob/master/contributing.md#how-to-make-an-entropy-source
    // to learn how entropy source works and how to make your own.
    // The sources run in this exact order.
    // The asynchronous sources are at the start to run in parallel with other sources.
    fonts: getFonts,
    domBlockers: getDomBlockers,
    fontPreferences: getFontPreferences,
    audio: getAudioFingerprint,
    screenFrame: getRoundedScreenFrame,
    osCpu: getOsCpu,
    languages: getLanguages2,
    colorDepth: getColorDepth,
    deviceMemory: getDeviceMemory,
    screenResolution: getScreenResolution,
    hardwareConcurrency: getHardwareConcurrency,
    timezone: getTimezone,
    sessionStorage: getSessionStorage,
    localStorage: getLocalStorage,
    indexedDB: getIndexedDB,
    openDatabase: getOpenDatabase,
    cpuClass: getCpuClass,
    platform: getPlatform,
    plugins: getPlugins,
    canvas: getCanvasFingerprint,
    touchSupport: getTouchSupport,
    vendor: getVendor,
    vendorFlavors: getVendorFlavors,
    cookiesEnabled: areCookiesEnabled,
    colorGamut: getColorGamut,
    invertedColors: areColorsInverted,
    forcedColors: areColorsForced,
    monochrome: getMonochromeDepth,
    contrast: getContrastPreference,
    reducedMotion: isMotionReduced,
    hdr: isHDR,
    math: getMathFingerprint,
    videoCard: getVideoCard,
    pdfViewerEnabled: isPdfViewerEnabled,
    architecture: getArchitecture
  };
  function loadBuiltinSources(options) {
    return loadSources(sources2, options, []);
  }
  var commentTemplate = "$ if upgrade to Pro: https://fpjs.dev/pro";
  function getConfidence(components) {
    var openConfidenceScore = getOpenConfidenceScore(components);
    var proConfidenceScore = deriveProConfidenceScore(openConfidenceScore);
    return { score: openConfidenceScore, comment: commentTemplate.replace(/\$/g, "".concat(proConfidenceScore)) };
  }
  function getOpenConfidenceScore(components) {
    if (isAndroid2()) {
      return 0.4;
    }
    if (isWebKit()) {
      return isDesktopSafari() ? 0.5 : 0.3;
    }
    var platform = components.platform.value || "";
    if (/^Win/.test(platform)) {
      return 0.6;
    }
    if (/^Mac/.test(platform)) {
      return 0.5;
    }
    return 0.7;
  }
  function deriveProConfidenceScore(openConfidenceScore) {
    return round(0.99 + 0.01 * openConfidenceScore, 1e-4);
  }
  function componentsToCanonicalString(components) {
    var result = "";
    for (var _i = 0, _a = Object.keys(components).sort(); _i < _a.length; _i++) {
      var componentKey = _a[_i];
      var component = components[componentKey];
      var value = component.error ? "error" : JSON.stringify(component.value);
      result += "".concat(result ? "|" : "").concat(componentKey.replace(/([:|\\])/g, "\\$1"), ":").concat(value);
    }
    return result;
  }
  function componentsToDebugString(components) {
    return JSON.stringify(components, function(_key, value) {
      if (value instanceof Error) {
        return errorToObject(value);
      }
      return value;
    }, 2);
  }
  function hashComponents(components) {
    return x64hash128(componentsToCanonicalString(components));
  }
  function makeLazyGetResult(components) {
    var visitorIdCache;
    var confidence = getConfidence(components);
    return {
      get visitorId() {
        if (visitorIdCache === void 0) {
          visitorIdCache = hashComponents(this.components);
        }
        return visitorIdCache;
      },
      set visitorId(visitorId) {
        visitorIdCache = visitorId;
      },
      confidence,
      components,
      version: version2
    };
  }
  function prepareForSources(delayFallback) {
    if (delayFallback === void 0) {
      delayFallback = 50;
    }
    return requestIdleCallbackIfAvailable(delayFallback, delayFallback * 2);
  }
  function makeAgent(getComponents, debug) {
    var creationTime = Date.now();
    return {
      get: function(options) {
        return __awaiter(this, void 0, void 0, function() {
          var startTime, components, result;
          return __generator(this, function(_a) {
            switch (_a.label) {
              case 0:
                startTime = Date.now();
                return [4, getComponents()];
              case 1:
                components = _a.sent();
                result = makeLazyGetResult(components);
                if (debug || (options === null || options === void 0 ? void 0 : options.debug)) {
                  console.log("Copy the text below to get the debug data:\n\n```\nversion: ".concat(result.version, "\nuserAgent: ").concat(navigator.userAgent, "\ntimeBetweenLoadAndGet: ").concat(startTime - creationTime, "\nvisitorId: ").concat(result.visitorId, "\ncomponents: ").concat(componentsToDebugString(components), "\n```"));
                }
                return [2, result];
            }
          });
        });
      }
    };
  }
  function monitor2() {
    if (window.__fpjs_d_m || Math.random() >= 1e-3) {
      return;
    }
    try {
      var request = new XMLHttpRequest();
      request.open("get", "https://m1.openfpcdn.io/fingerprintjs/v".concat(version2, "/npm-monitoring"), true);
      request.send();
    } catch (error) {
      console.error(error);
    }
  }
  function load2(_a) {
    var _b = _a === void 0 ? {} : _a, delayFallback = _b.delayFallback, debug = _b.debug, _c = _b.monitoring, monitoring = _c === void 0 ? true : _c;
    return __awaiter(this, void 0, void 0, function() {
      var getComponents;
      return __generator(this, function(_d) {
        switch (_d.label) {
          case 0:
            if (monitoring) {
              monitor2();
            }
            return [4, prepareForSources(delayFallback)];
          case 1:
            _d.sent();
            getComponents = loadBuiltinSources({ debug });
            return [2, makeAgent(getComponents, debug)];
        }
      });
    });
  }

  // ../../node_modules/.pnpm/detectincognitojs@1.5.0/node_modules/detectincognitojs/dist/detectIncognito.esm.js
  var e = { d: (t2, n2) => {
    for (var r2 in n2) e.o(n2, r2) && !e.o(t2, r2) && Object.defineProperty(t2, r2, { enumerable: true, get: n2[r2] });
  }, o: (e2, t2) => Object.prototype.hasOwnProperty.call(e2, t2) };
  var t = {};
  e.d(t, { A: () => a, k: () => o });
  var n = function(e2, t2, n2, r2) {
    return new (n2 || (n2 = Promise))(function(o2, a2) {
      function i2(e3) {
        try {
          u(r2.next(e3));
        } catch (e4) {
          a2(e4);
        }
      }
      function c2(e3) {
        try {
          u(r2.throw(e3));
        } catch (e4) {
          a2(e4);
        }
      }
      function u(e3) {
        var t3;
        e3.done ? o2(e3.value) : (t3 = e3.value, t3 instanceof n2 ? t3 : new n2(function(e4) {
          e4(t3);
        })).then(i2, c2);
      }
      u((r2 = r2.apply(e2, t2 || [])).next());
    });
  };
  var r = function(e2, t2) {
    var n2, r2, o2, a2, i2 = { label: 0, sent: function() {
      if (1 & o2[0]) throw o2[1];
      return o2[1];
    }, trys: [], ops: [] };
    return a2 = { next: c2(0), throw: c2(1), return: c2(2) }, "function" == typeof Symbol && (a2[Symbol.iterator] = function() {
      return this;
    }), a2;
    function c2(c3) {
      return function(u) {
        return function(c4) {
          if (n2) throw new TypeError("Generator is already executing.");
          for (; a2 && (a2 = 0, c4[0] && (i2 = 0)), i2; ) try {
            if (n2 = 1, r2 && (o2 = 2 & c4[0] ? r2.return : c4[0] ? r2.throw || ((o2 = r2.return) && o2.call(r2), 0) : r2.next) && !(o2 = o2.call(r2, c4[1])).done) return o2;
            switch (r2 = 0, o2 && (c4 = [2 & c4[0], o2.value]), c4[0]) {
              case 0:
              case 1:
                o2 = c4;
                break;
              case 4:
                return i2.label++, { value: c4[1], done: false };
              case 5:
                i2.label++, r2 = c4[1], c4 = [0];
                continue;
              case 7:
                c4 = i2.ops.pop(), i2.trys.pop();
                continue;
              default:
                if (!(o2 = i2.trys, (o2 = o2.length > 0 && o2[o2.length - 1]) || 6 !== c4[0] && 2 !== c4[0])) {
                  i2 = 0;
                  continue;
                }
                if (3 === c4[0] && (!o2 || c4[1] > o2[0] && c4[1] < o2[3])) {
                  i2.label = c4[1];
                  break;
                }
                if (6 === c4[0] && i2.label < o2[1]) {
                  i2.label = o2[1], o2 = c4;
                  break;
                }
                if (o2 && i2.label < o2[2]) {
                  i2.label = o2[2], i2.ops.push(c4);
                  break;
                }
                o2[2] && i2.ops.pop(), i2.trys.pop();
                continue;
            }
            c4 = t2.call(e2, i2);
          } catch (e3) {
            c4 = [6, e3], r2 = 0;
          } finally {
            n2 = o2 = 0;
          }
          if (5 & c4[0]) throw c4[1];
          return { value: c4[0] ? c4[1] : void 0, done: true };
        }([c3, u]);
      };
    }
  };
  function o() {
    return n(this, void 0, Promise, function() {
      return r(this, function(e2) {
        switch (e2.label) {
          case 0:
            return [4, new Promise(function(e3, t2) {
              var o2 = "Unknown", a2 = false;
              function i2(t3) {
                a2 || (a2 = true, e3({ isPrivate: t3, browserName: o2 }));
              }
              function c2() {
                var e4 = 0, t3 = parseInt("-1");
                try {
                  t3.toFixed(t3);
                } catch (t4) {
                  e4 = t4.message.length;
                }
                return e4;
              }
              function u() {
                return void 0 !== navigator.msSaveBlob && function(e4) {
                  try {
                    return e4 === eval.toString().length;
                  } catch (e5) {
                    return false;
                  }
                }(39);
              }
              function s() {
                var e4;
                return n(this, void 0, void 0, function() {
                  var t3, n2;
                  return r(this, function(r2) {
                    switch (r2.label) {
                      case 0:
                        return r2.trys.push([0, 2, , 3]), [4, navigator.storage.getDirectory()];
                      case 1:
                        return r2.sent(), i2(false), [3, 3];
                      case 2:
                        return t3 = r2.sent(), n2 = t3, t3 instanceof Error && (n2 = null !== (e4 = t3.message) && void 0 !== e4 ? e4 : t3), "string" != typeof n2 ? (i2(false), [2]) : (i2(!!n2.includes("unknown transient reason")), [3, 3]);
                      case 3:
                        return [2];
                    }
                  });
                });
              }
              function l() {
                var e4;
                return n(this, void 0, Promise, function() {
                  return r(this, function(t3) {
                    switch (t3.label) {
                      case 0:
                        return void 0 === (null === (e4 = navigator.storage) || void 0 === e4 ? void 0 : e4.getDirectory) ? [3, 2] : [4, s()];
                      case 1:
                        return t3.sent(), [3, 3];
                      case 2:
                        void 0 !== navigator.maxTouchPoints ? function() {
                          var e5 = String(Math.random());
                          try {
                            var t4 = indexedDB.open(e5, 1);
                            t4.onupgradeneeded = function(t5) {
                              var n2 = t5.target.result, r2 = function(e6) {
                                i2(e6);
                              };
                              try {
                                n2.createObjectStore("t", { autoIncrement: true }).put(new Blob()), r2(false);
                              } catch (e6) {
                                (e6.message || "").includes("are not yet supported") ? r2(true) : r2(false);
                              } finally {
                                n2.close(), indexedDB.deleteDatabase(e5);
                              }
                            }, t4.onerror = function() {
                              return i2(false);
                            };
                          } catch (e6) {
                            i2(false);
                          }
                        }() : function() {
                          var e5 = window.openDatabase, t4 = window.localStorage;
                          try {
                            e5(null, null, null, null);
                          } catch (e6) {
                            return void i2(true);
                          }
                          try {
                            t4.setItem("test", "1"), t4.removeItem("test");
                          } catch (e6) {
                            return void i2(true);
                          }
                          i2(false);
                        }(), t3.label = 3;
                      case 3:
                        return [2];
                    }
                  });
                });
              }
              function f() {
                navigator.webkitTemporaryStorage.queryUsageAndQuota(function(e4, t3) {
                  var n2;
                  i2(Math.round(t3 / 1048576) < 2 * Math.round((void 0 !== (n2 = window).performance && void 0 !== n2.performance.memory && void 0 !== n2.performance.memory.jsHeapSizeLimit ? performance.memory.jsHeapSizeLimit : 1073741824) / 1048576));
                }, function(e4) {
                  t2(new Error("detectIncognito somehow failed to query storage quota: " + e4.message));
                });
              }
              function d() {
                void 0 !== self.Promise && void 0 !== self.Promise.allSettled ? f() : (0, window.webkitRequestFileSystem)(0, 1, function() {
                  i2(false);
                }, function() {
                  i2(true);
                });
              }
              (function() {
                return n(this, void 0, Promise, function() {
                  return r(this, function(e4) {
                    switch (e4.label) {
                      case 0:
                        return 44 !== c2() ? [3, 2] : (o2 = "Safari", [4, l()]);
                      case 1:
                        return e4.sent(), [3, 3];
                      case 2:
                        51 === c2() ? (n2 = navigator.userAgent, o2 = n2.match(/Chrome/) ? void 0 !== navigator.brave ? "Brave" : n2.match(/Edg/) ? "Edge" : n2.match(/OPR/) ? "Opera" : "Chrome" : "Chromium", d()) : 25 === c2() ? (o2 = "Firefox", i2(void 0 === navigator.serviceWorker)) : u() ? (o2 = "Internet Explorer", i2(void 0 === window.indexedDB)) : t2(new Error("detectIncognito cannot determine the browser")), e4.label = 3;
                      case 3:
                        return [2];
                    }
                    var n2;
                  });
                });
              })().catch(t2);
            })];
          case 1:
            return [2, e2.sent()];
        }
      });
    });
  }
  "undefined" != typeof window && (window.detectIncognito = o);
  var a = o;
  var i = t.A;
  var c = t.k;

  // src/verify-client.ts
  async function withTimeout(promise, timeoutMs, errorMessage) {
    return Promise.race([
      promise,
      new Promise((_, reject) => {
        setTimeout(() => reject(new Error(errorMessage)), timeoutMs);
      })
    ]);
  }
  function createIngestPayload(visitorId) {
    return {
      visitorId,
      url: window.location.href
    };
  }
  function createVerifyPayload(visitorId, botResult, incognitoResult, isFallback) {
    const payload = { visitorId };
    if (isFallback) {
      payload.isFallback = true;
    }
    if (botResult) {
      payload.bot = {
        botProbability: botResult.bot ? 1 : 0,
        botType: botResult.bot ? botResult.botKind || "unknown" : "unknown",
        botSignature: null
      };
    } else {
      payload.bot = {
        botProbability: isFallback ? null : -1,
        botType: isFallback ? null : "detection_failed",
        botSignature: null
      };
    }
    if (incognitoResult) {
      payload.incognito = {
        isPrivate: incognitoResult.isPrivate,
        browserName: incognitoResult.browserName
      };
    }
    return payload;
  }
  async function sendVerifyRequest(payload) {
    return fetch("/verify", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
  }
  async function ingestRequest(payload) {
    return fetch("/api/v1/ingest", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
  }
  (async () => {
    try {
      if (document.cookie?.includes("ocfp=")) {
        return;
      }
      const loadOptions = {};
      const fpPromise = load2(loadOptions).catch((error) => {
        console.log("FingerprintJS load error (caught early):", error);
        return null;
      });
      const botdPromise = load().catch((error) => {
        console.log("BotD load error (caught early):", error);
        return null;
      });
      let fp = null;
      try {
        fp = await withTimeout(fpPromise, 3e3, "FP load timeout");
        if (!fp) {
          throw new Error("FingerprintJS failed to load");
        }
      } catch (error) {
        console.log("FingerprintJS load error:", error);
        throw error;
      }
      let botd = null;
      try {
        botd = await withTimeout(botdPromise, 3e3, "BotD load timeout");
      } catch (error) {
        console.log("BotD load error:", error);
      }
      let result;
      try {
        result = await withTimeout(fp.get(), 3e3, "FP get timeout");
      } catch (error) {
        console.log("Fingerprint get error:", error);
        throw error;
      }
      let botdResult = null;
      if (botd) {
        try {
          botdResult = await withTimeout(Promise.resolve(botd.detect()), 3e3, "BotD detect timeout");
        } catch (error) {
          console.log("BotD detection error:", error);
        }
      }
      const visitorId = result.visitorId;
      let incognitoResult = null;
      try {
        incognitoResult = await c();
        console.log("Incognito detection:", {
          isPrivate: incognitoResult.isPrivate,
          browserName: incognitoResult.browserName
        });
      } catch (error) {
        console.log("Incognito detection error:", error);
      }
      try {
        console.log("Sending fingerprint and bot data to verify endpoint");
        const payload = createVerifyPayload(visitorId, botdResult, incognitoResult);
        const response = await sendVerifyRequest(payload);
        if (response.ok) {
          await ingestRequest(createIngestPayload(visitorId));
        }
      } catch (fetchError) {
        console.log("Fetch error:", fetchError);
      }
    } catch (error) {
      console.log("Fingerprint error:", error);
      try {
        const basicFingerprint = {
          userAgent: navigator.userAgent,
          language: navigator.language,
          screenSize: `${window.screen.width}x${window.screen.height}`
        };
        const fallbackVisitorId = `${btoa(JSON.stringify(basicFingerprint)).substring(0, 16)}`;
        const fallbackPayload = createVerifyPayload(fallbackVisitorId, null, null, true);
        const response = await sendVerifyRequest(fallbackPayload);
        if (response.ok) {
          await ingestRequest(createIngestPayload(fallbackVisitorId));
        }
      } catch (fallbackError) {
        console.log("Fallback fingerprint failed:", fallbackError);
      }
    }
  })();
})();
/*! Bundled license information:

detectincognitojs/dist/detectIncognito.esm.js:
  (*!
   *
   * detectIncognito v1.5.0
   *
   * https://github.com/Joe12387/detectIncognito
   *
   * MIT License
   *
   * Copyright (c) 2021 - 2025 Joe Rutkowski <Joe@dreggle.com>
   *
   * Permission is hereby granted, free of charge, to any person obtaining a copy
   * of this software and associated documentation files (the "Software"), to deal
   * in the Software without restriction, including without limitation the rights
   * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
   * copies of the Software, and to permit persons to whom the Software is
   * furnished to do so, subject to the following conditions:
   *
   * The above copyright notice and this permission notice shall be included in all
   * copies or substantial portions of the Software.
   *
   * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
   * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
   * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
   * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
   * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
   * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
   * SOFTWARE.
   *
   * Please keep this comment intact in order to properly abide by the MIT License.
   *
   **)
*/

"use strict";
var badge_style = {
    running: 'info',
    exited: 'secondary',
    created: 'secondary',
    removing: 'secondary',
    'new': 'dark',
    deployed: 'info',
    undeployed: 'secondary',
    Success: 'secondary',
    Error: 'danger',
    Queued: 'dark',
    Building: 'dark',
};

var ws_link = wsLink();
setInterval("ws_link.check()", 1200);

function wsLink() {
    var ws = new WebSocket("ws://" + window.location.host + "/link");
    ws.onmessage = function (e) {
        var data = JSON.parse(e.data);
        console.log("websocket data:");
        console.log(data);
        if (data.hasOwnProperty("images"))
            window.appView.images = data.images;
        if (data.hasOwnProperty("containers"))
            window.appView.containers = data.containers;
        if (data.hasOwnProperty("unused_volumes"))
            window.appView.unused_volumes = data.unused_volumes;
        if (data.hasOwnProperty("result"))
            window.alertBox.show(data.result, data.content);
        if (data.hasOwnProperty("notification"))
            window.appView.notify(data.notification);
    }
    ws.onopen = function () {
        window.alertBox.show("success", "Connected.");
    }
    ws.onclose = function () {
        console.log("ws close");
    };
    ws.onerror = function () {
        console.log("ws error");
    };
    ws.check = function () {
        if (this.readyState === 3) {
            window.alertBox.show("danger", "Connection lost! Reconnecting...");
            ws_link = wsLink();
        }
    };
    return ws;
}

var server = new Proxy(function () {}, {
        get: function (target, property, receiver) {
            console.log('load rpc method: ' + property);
            return function () {
                window.alertBox.show("warning", "");
                var kwargs = {
                    method: property,
                    args: arguments,
                };
                console.log("RPC command: " + JSON.stringify(kwargs));
                ws_link.send(JSON.stringify(kwargs));
            };
        }
    });

window.alertBox = new Vue({
        delimiters: ['${', '}'],
        el: "#v-alert",
        data() {
            return {
                dismissCountDown: 0,
                content: '',
                title: '',
                class_style: 'success'
            }
        },
        methods: {
            countDownChanged(dismissCountDown) {
                this.dismissCountDown = dismissCountDown
            },
            show(type, content) {
                var title_map = {
                    "info": "Info",
                    "danger": "Error!",
                    "success": "Success!",
                    "warning": "dealing...",
                };
                this.class_style = type;
                this.title = title_map[type];
                this.content = content;
                if (type === "warning")
                    this.dismissCountDown = 999;
                else if (type === 'danger')
                    this.dismissCountDown = 9;
                else
                    this.dismissCountDown = 5;
            }
        }
    });

window.appView = new Vue({
        delimiters: ['${', '}'],
        el: '#v-view',
        data: {
            images: [],
            containers: [],
            unused_volumes: 0,
            badge: badge_style,
        },
        updated: function () {
            this.$nextTick(function () {
                $("input[type=checkbox]").bootstrapSwitch('destroy');
                $("input[type=checkbox]").bootstrapSwitch({
                    size: 'small',
                    onSwitchChange: function (event, state) {
                        event.preventDefault();
                        var image = $(this).data('target');
                        server.makeautodeploy(image, state);
                    },
                });
            })
        },
        methods: {
            test: server.test,
            prune: server.prune,
            pruneall: server.pruneall,
            deployImage: server.deploy,
            removeImage: function (obj) {
                console.log("remove image " + obj);
                if (confirm("remove image " + obj + "?"))
                    server.remove(obj);
            },
            startContainer: function (obj) {
                console.log("start container " + obj);
                server.container("start", obj);
            },
            stopContainer: function (obj) {
                console.log("stop container " + obj);
                server.container("stop", obj);
            },
            removeContainer: function (obj) {
                console.log("remove container " + obj);
                if (confirm("remove container " + obj + " ?"))
                    server.container("remove", obj);
            },
            notify: function (msg) {
                if (window.Notification && Notification.permission !== "denied") {
                    Notification.requestPermission(function (status) {
                        var notice_ = new Notification('Cap notification', {
                                body: msg
                            });
                    });
                }
            }
        },
    });

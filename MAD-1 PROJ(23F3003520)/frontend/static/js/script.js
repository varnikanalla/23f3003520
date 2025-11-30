window.onload = function () {
    var alerts = document.querySelectorAll(".alert");
    for (var i = 0; i < alerts.length; i++) {
        setTimeout(function (a) { a.style.display = "none"; }, 5000, alerts[i]);
    }
};

var forms = document.querySelectorAll(".needs-validation");
for (var i = 0; i < forms.length; i++) {
    forms[i].onsubmit = function (e) {
        if (!this.checkValidity()) {
            e.preventDefault();
        }
    };
}

console.log("Loaded");

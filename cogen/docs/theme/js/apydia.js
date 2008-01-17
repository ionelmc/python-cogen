$(function () {
    $("a[href ^= 'http://']").click(function () {
        window.open(this.href); return false;
    });
});
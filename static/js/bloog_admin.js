/**
 The MIT License
 
 Copyright (c) 2008 William T. Katz
 
 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to 
 deal in the Software without restriction, including without limitation 
 the rights to use, copy, modify, merge, publish, distribute, sublicense, 
 and/or sell copies of the Software, and to permit persons to whom the 
 Software is furnished to do so, subject to the following conditions:
 
 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.
 
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER 
 DEALINGS IN THE SOFTWARE.
**/

YAHOO.namespace("bloog");
function showRTE(e, isArticle) {
    var hdr = $('div#myDialog div.hd');
    if (isArticle) {
        hdr.setContent('Submit Article');
    } else {
        hdr.setContent('Submit Blog Entry');
        var today = new Date();
        var month = today.getMonth() + 1;
        var year = today.getFullYear();
        document.getElementById("dlgForm").action = "/" + year + "/" + month;
    }
    YAHOO.bloog.myDialog.show();
}
function initAdmin() {
    var handleCancel = function() {
        this.cancel();
    }
    var handleSubmit = function() {
        YAHOO.bloog.editor.saveHTML();
        this.submit();
    }
    YAHOO.namespace("bloog");
    YAHOO.bloog.myDialog = new YAHOO.widget.Dialog(
        "myDialog", {
            width: "550px",
            fixedcenter: true,
            visible: false,
            modal: true,
            constraintoviewpoint: true,
            buttons: [ { text: "Submit", handler: handleSubmit, 
                         isDefault:true },
                       { text: "Cancel", handler: handleCancel } ]
        });
    YAHOO.bloog.editor = new YAHOO.widget.Editor(
        'body', {
            height: '300px',
            width: '500px',
            dompath: true,
            animate: true
        });
    YAHOO.bloog.editor.render();
    
    YAHOO.bloog.myDialog.validate = function() {
        var data = this.getData();
        if (data.title == "") {
            alert("Please enter a title for this post.");
            return false;
        }
        return true;
    }
    var handleSuccess = function(o) {
        var response = o.responseText;
        response = response.split("<!")[0];
        $('div#bloogResponse').setContent(response);
        YAHOO.bloog.respDialog.show();
    };
    var handleFailure = function(o) {
        alert("Submission failed: " + o.status);
    };
    YAHOO.bloog.myDialog.callback = { success: handleSuccess, 
                                      failure: handleFailure };
    YAHOO.bloog.myDialog.render();
    
    var forceUpdate = function(o) {
        window.location = "/";
    }
    YAHOO.bloog.respDialog = new YAHOO.widget.Dialog(
        "responseDialog", {
            fixedcenter: true,
            visible: false,
            modal: true,
            constraintoviewpoint: true,
            close: false,
            buttons: [ { text: "Home Page", handler: forceUpdate, 
                         isDefault: true }]
        });
    YAHOO.bloog.respDialog.render();

    YAHOO.util.Event.addListener("newarticle", "click", showRTE, true);
    YAHOO.util.Event.addListener("newblog", "click", showRTE, false);      
}

YAHOO.util.Event.onDOMReady(initAdmin);

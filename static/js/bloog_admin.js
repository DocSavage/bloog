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
YAHOO.bloog.initAdmin = function() {

    var forceUpdate = function(o) {
        window.location = "/";
    }
    var showNewRTE = function(e, isArticle) {
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
    var showEditRTE = function(e) {
        if (this.id == 'editbtn') {
            $('div#myDialog div.hd').setContent('Edit Article');
            var article_body = document.getElementById("post-").innerHTML;
            $('#body').setContent(article_body);
        }
        YAHOO.bloog.myDialog.show();
    }
    var showDeleteDialog = function(e) {
        YAHOO.bloog.deleteDialog.show();
    }

    var handleSuccess = function(o) {
        var response = o.responseText;
        response = response.split("<!")[0];
        // Redirect to this new URL
        window.location = response;
    };
    var handleFailure = function(o) {
        alert("Submission failed: " + o.status);
    };
    var handleCancel = function() {
        this.cancel();
    }
    var handleNewSubmit = function() {
        YAHOO.bloog.editor.saveHTML();
        this.submit();
    }
    var handleEditSubmit = function() {
        YAHOO.bloog.editor.saveHTML();
        var formObj = document.getElementById("dlgForm");
        YAHOO.util.Connect.setForm(formObj);
        var cObj = YAHOO.util.Connect.asyncRequest('PUT', formObj.action, {success: handleSuccess, failure: handleFailure})
    }
    YAHOO.namespace("bloog");
    YAHOO.bloog.myDialog = new YAHOO.widget.Dialog(
        "myDialog", {
            width: "550px",
            fixedcenter: true,
            visible: false,
            modal: true,
            constraintoviewpoint: true,
            buttons: [ { text: "Submit", handler: handleNewSubmit, 
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
    YAHOO.bloog.myDialog.callback = { success: handleSuccess, 
                                      failure: handleFailure };
    YAHOO.bloog.myDialog.render();

    YAHOO.bloog.deleteDialog = new YAHOO.widget.SimpleDialog(
        "confirmDlg", {
            width: "20em",
            effect: {effect:YAHOO.widget.ContainerEffect.FADE, duration:0.25},
            fixedcenter: true,
            modal: true,
            visible: false,
            draggable: false
        })
    YAHOO.bloog.deleteDialog.setHeader("Warning");
    YAHOO.bloog.deleteDialog.setBody("Are you sure you want to delete this post?");

    var handleDelete = function() {
        var cObj = YAHOO.util.Connect.asyncRequest(
            'DELETE',
            '#', 
            {success: handleSuccess, failure: handleFailure}
        );
    }
    var myButtons = [ { text: "Delete!", 
                        handler: handleDelete },
                      { text: "Cancel", 
                        handler: function() { this.hide(); },
                        isDefault: true }
                    ];
    YAHOO.bloog.deleteDialog.cfg.queueProperty("buttons", myButtons);
    YAHOO.bloog.deleteDialog.render(document.body);
    
    YAHOO.util.Event.addListener("newarticle", "click", showNewRTE, true);
    YAHOO.util.Event.addListener("newblog", "click", showNewRTE, false);
    YAHOO.util.Event.addListener("editbtn", "click", showEditRTE);
    YAHOO.util.Event.addListener("deletebtn", "click", showDeleteDialog);
}

YAHOO.util.Event.onDOMReady(YAHOO.bloog.initAdmin);

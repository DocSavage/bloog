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

    var showRTE = function(e) {
        var hdr = $('div#myDialog div.hd');
        YAHOO.bloog.http = {};
        switch (this.id) {
            case 'newarticle':
                hdr.setContent('Submit Article');
                YAHOO.bloog.http.action = '/';
                YAHOO.bloog.http.verb = 'POST';
                YAHOO.bloog.editor.setEditorHTML('<p>Article goes here</p>');
                break;
            case 'newblog':
                hdr.setContent('Submit Blog Entry');
                var today = new Date();
                var month = today.getMonth() + 1;
                var year = today.getFullYear();
                YAHOO.bloog.http.action = "/" + year + "/" + month;
                YAHOO.bloog.http.verb = 'POST';
                YAHOO.bloog.editor.setEditorHTML('<p>Blog entry goes here</p>');
                break;
            case 'editbtn':
                hdr.setContent('Submit Edit');
                YAHOO.bloog.http.action = '#';
                YAHOO.bloog.http.verb = 'PUT';
                // Parse the current article HTML into title, tags, and body.
                var blog_title = document.getElementById("blogtitle").innerHTML;
                var blog_body =  document.getElementById("blogbody").innerHTML;
                //$('#title').setContent(blog_title);
                YAHOO.bloog.editor.setEditorHTML(blog_body);
                break;
        }
        YAHOO.bloog.myDialog.show();
    }

    var showDeleteDialog = function(e) {
        YAHOO.bloog.deleteDialog.show();
    }

    var handleSuccess = function(o) {
        var response = o.responseText;
        response = response.split("<!")[0];
        // Redirect to this new URL -- For some reason this has problems in Safari
        window.location.href = response;
    };
    var handleFailure = function(o) {
        alert("Submission failed: " + o.status);
    };
    var handleCancel = function() {
        this.cancel();
    }
    var handleSubmit = function() {
        YAHOO.bloog.editor.saveHTML();
        var html = YAHOO.bloog.editor.get('element').value;
        var title = YAHOO.util.Dom.get('title').value;
        var tags = YAHOO.util.Dom.get('tags').value;
        var postData = 'title=' + encodeURIComponent(title) + '&' +
                        'tags=' + encodeURIComponent(tags) + '&' +
                        'body=' + encodeURIComponent(html);
        var cObj = YAHOO.util.Connect.asyncRequest(
            YAHOO.bloog.http.verb, 
            YAHOO.bloog.http.action, 
            {success: handleSuccess, failure: handleFailure},
            postData);
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
    YAHOO.bloog.myDialog.callback = { success: handleSuccess, 
                                      failure: handleFailure };
    YAHOO.bloog.myDialog.render();

    var handleDelete = function() {
        var cObj = YAHOO.util.Connect.asyncRequest(
            'DELETE',
            '#', 
            {success: handleSuccess, failure: handleFailure}
        );
    }
    YAHOO.bloog.deleteDialog = new YAHOO.widget.SimpleDialog(
        "confirmDlg", {
            width: "20em",
            effect: {effect:YAHOO.widget.ContainerEffect.FADE, duration:0.25},
            fixedcenter: true,
            modal: true,
            visible: false,
            draggable: false,
            buttons: [ { text: "Delete!", handler: handleDelete },
                       { text: "Cancel", 
                         handler: function() { this.hide(); },
                         isDefault: true } ]
        })
    YAHOO.bloog.deleteDialog.setHeader("Warning");
    YAHOO.bloog.deleteDialog.setBody("Are you sure you want to delete this post?");

    YAHOO.bloog.deleteDialog.render(document.body);
    
    YAHOO.util.Event.addListener("newarticle", "click", showRTE);
    YAHOO.util.Event.addListener("newblog", "click", showRTE);
    YAHOO.util.Event.addListener("editbtn", "click", showRTE);
    YAHOO.util.Event.addListener("deletebtn", "click", showDeleteDialog);
}

YAHOO.util.Event.onDOMReady(YAHOO.bloog.initAdmin);

function toggleDiv(divid){
  if(document.getElementById(divid).style.display == 'none'){
    document.getElementById(divid).style.display = 'block';
  }else{
    document.getElementById(divid).style.display = 'none';
  }
}
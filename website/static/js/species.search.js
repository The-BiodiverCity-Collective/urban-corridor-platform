$(function(){
  search_url = "/ajax/species/"; 
  if (search_active_only) {
    search_url += "?active_only=true"; 
  }
  $("#search_species").select2({
    minimumInputLength: 3,
    ajax: {
      delay: 150,
      url: search_url,
      dataType: "json",
      processResults: function(data) {
        return {
          results: $.map(data, function(item) {
            return {
              id: item.id,
              text: item.name,
              common_name: item.common_name,
              active: item.active
            };
          })
        };
      }
    },
    templateResult: function(item) {
      const dotColor = item.active ? "text-lime-500" : "text-gray-700";
      const dotIcon = item.active ? "fa-circle" : "fa-circle" + " text-gray-700";
      
      return $("<div class='flex items-center'>" +
               "<i class='fa " + dotColor + " " + dotIcon + "'></i>" +
               "<em class='ml-2 " + (item.active ? "text-black" : "text-gray-700") + "'>" + item.text + "</em>" + 
               "<strong class='ml-2 " + (item.active ? "text-black" : "text-gray-700") + "'>" + (item.common_name || "") + "</strong>" + 
               "</div>");
    }
  }).on("select2:select", function (e) {
    const id = e.params.data.id;
    window.location.href = getRedirectURL(id);
  });

});

// Select all elements with the class "border-l-2"
var elements = document.querySelectorAll('.border-l-2');
var alll = "";

// Iterate over the selected elements
elements.forEach(function(element) {
        // Access the HTML content of each element
        //console.log(element.innerHTML);
    var htmlContent = element.innerHTML;

    // Create a temporary element to parse the HTML
    var tempElement = document.createElement('div');
    tempElement.innerHTML = htmlContent;

    // Select all paragraph elements containing station-time pairs
    var paragraphElements = tempElement.querySelectorAll('p');

    // Initialize an array to store station-time pairs
    var stationTimePairs = [];

    // Iterate over paragraph elements to extract station-time pairs
    paragraphElements.forEach(function(paragraph) {
        // Get the station and time elements
        var station = paragraph.querySelector('span.mr-2').textContent;
        var time = paragraph.querySelector('span.font-bold').textContent;
        
        // Add the station-time pair to the array
        stationTimePairs.push([station, time]);
    });

    // Print the array of station-time pairs

    alll = alll + JSON.stringify(stationTimePairs)
});

console.log(alll)

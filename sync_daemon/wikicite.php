<html>
<head>
<?php

include "settings.php";

$wiki_key = $_GET['wiki_id'];
$zotero_key = $_GET['zotero_id'];
$wiki_url_tmp = $_GET['wiki_url'];

if (strlen($wiki_url_tmp) > 0) $wiki_url = $wiki_url_tmp;

$conn = new mysqli($db_servername, $db_username, $db_password, $db_dbname);
if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
 }

for ($i = 0; $i < 1; $i++) {
    if (!is_null($wiki_key)) {
        $sql = "SELECT zotero_id FROM id_links WHERE wiki_id = '$wiki_key'";
        $result = $conn->query($sql);
        
        if ($result->num_rows > 0) {
            $row = $result->fetch_assoc();
            echo "<META http-equiv=\"refresh\" content=\"0;URL=https://www.zotero.org/groups/" . $zotero_group . "/items/itemKey/" . $row["zotero_id"] ."\" > ";
            break;
        }
    } else {
        $sql = "SELECT wiki_id FROM id_links WHERE zotero_id = '$zotero_key'";
        $result = $conn->query($sql);
        
        if ($result->num_rows > 0) {
            $row = $result->fetch_assoc();
            echo "<META http-equiv=\"refresh\" content=\"0;URL=" . $wiki_url . "index.php/" . $row["wiki_id"] ."\" > ";
            break;
        }
    }
?>
</head>
<body>
<?php
    // If there are no results in the linking database, run they syncing daemon to see if these were added since.
    if ($result->num_rows == 0) {
        if ($i == 0) {
            shell_exec ( "python synclibrary.py" );
            continue;
        }
?>

 
<title>Redirect between Zotero and wiki</title>
</head>
<body>


<?php
        echo "0 results";
    }
}
$conn->close();

?>
</body>
</html>
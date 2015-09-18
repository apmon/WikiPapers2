{

<?php

include "settings.php";

    if (array_key_exists( 'wiki_id', $_GET)) {
        $wiki_key = $_GET['wiki_id'];
    } else {
        $wiki_key = NULL;
    }
    if (array_key_exists( 'zotero_id', $_GET)) {
        $zotero_key = $_GET['zotero_id'];
    } else {
        $zotero_key = NULL;
    }

    if (is_null($zotero_key) && is_null($wiki_key)) {
        echo "Neither wiki_id nor zotero_id specified. Please provide either in the URL";
        echo " }";
        return;
    }

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
            echo "\"zotero_id\": \"" . $row["zotero_id"] . "\",\n";
            echo "\"wiki_id\": \"" . $wiki_key . "\"\n";
            break;
        }
    } else {
        $sql = "SELECT wiki_id FROM id_links WHERE zotero_id = '$zotero_key'";
        $result = $conn->query($sql);
        
        if ($result->num_rows > 0) {
            $row = $result->fetch_assoc();
            echo "\"zotero_id\": \"" . $zotero_key . "\"";
            echo "\"wiki_id\": \"" . $row["wiki_id"] . "\"";
            break;
        }
    }

    // If there are no results in the linking database, run they syncing daemon to see if these were added since.
    if ($result->num_rows == 0) {
        if ($i == 0) {
            shell_exec ( "python synclibrary.py" );
            continue;
        }
    }
}

?>

}
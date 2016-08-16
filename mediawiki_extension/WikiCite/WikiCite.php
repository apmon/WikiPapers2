<?php
 
  // Take credit for your work.
$wgExtensionCredits['parserhook'][] = array(
 
                                            // The full path and filename of the file. This allows MediaWiki
                                            // to display the Subversion revision number on Special:Version.
                                            'path' => __FILE__,
                                            
                                            // The name of the extension, which will appear on Special:Version.
                                            'name' => 'WikiCite Parser Function',
 
                                            // A description of the extension, which will appear on Special:Version.
                                            'description' => 'A parser extension to integrate Zotero with Mediawiki',
 
                                            // Alternatively, you can specify a message key for the description.
                                            'descriptionmsg' => 'wikicite-desc',
 
                                            // The version of the extension, which will appear on Special:Version.
                                            // This can be a number or a string.
                                            'version' => 1, 
 
                                            // Your name, which will appear on Special:Version.
                                            'author' => 'Kai Krueger',
 
                                            // The URL to a wiki page/web page with information about the extension,
                                            // which will appear on Special:Version.
                                            'url' => 'https://grey.colorado.edu/ccnlab/index.php/WikiCite',
 
                                            );
 
// Specify the function that will initialize the parser function.
$wgHooks['ParserFirstCallInit'][] = 'WikiCiteSetupParserFunction';
 
// Allow translation of the parser function name
$wgExtensionMessagesFiles['WikiCite'] = __DIR__ . '/WikiCite.i18n.php';

$wgWikiCiteLinkerURL = 'https://grey.colorado.edu/wikicite/';
$wgWikiCiteZoteroGroupID = 340666;
$wgWikiCiteZoteroGroup = 'ccnlab';

// Tell MediaWiki that the parser function exists.
function WikiCiteSetupParserFunction( &$parser ) {
 
    // Create a function hook associating the "example" magic word with the
    // ExampleExtensionRenderParserFunction() function. See: the section 
    // 'setFunctionHook' below for details.
    $parser->setFunctionHook( 'citepaper', 'CitePaperInfoboxRenderParserFunction' );
    $parser->setFunctionHook( 'citepapertwo', 'CitePaperRenderParserFunction' );
    $parser->setFunctionHook( 'citetpaper', 'CitetPaperRenderParserFunction' );
    $parser->setFunctionHook( 'citereference', 'CiteReferenceRenderParserFunction' );
    $parser->setFunctionHook( 'citebibliography', 'CiteBibliographyRenderParserFunction' );
 
    // Return true so that MediaWiki continues to load extensions.
    return true;
}

include __DIR__ . '/CiteProc.php';

function RenderCite($cite_key = '', $cite_format = "p", $cite_style = "b") {
    global $wgWikiCiteLinkerURL;
    global $wgWikiCiteZoteroGroupID;
    global $wgWikiCiteZoteroGroup;

    $cite_keys = explode (",", $cite_key);

    $num_cite_keys = count($cite_keys);
    $cite_key_idx = 0;

    $output = "";
    
    foreach ($cite_keys as $cite_key) {

        $link_data = json_decode(file_get_contents($wgWikiCiteLinkerURL . 'wikicite_api.php?wiki_id=' . $cite_key)); 
    
        //Check if there is a page for this key on the wiki.
        //If yes, then we will link to our wiki, otherwise we
        //link to the zotero source entry
        $title = Title::newFromText($cite_key);
    
        if ( $title->exists() ) {
            $output = "[[";
            $output .= $cite_key;
            $output .= "|";
            //Check if the linking data actually returned an entry, if not, we can not create a correct citation
            //and thus just print the bibkey
            if (!property_exists($link_data, "zotero_id")) {
                $output .= $cite_key;
                $output .= "]]";
                $output_strings[$cite_key_idx] = $output;
                $cite_key_idx++;
                continue;
            }
            
        } else {
            //Check if the linking data actually returned an entry, if not, we can not create a correct citation
            //and thus just print the bibkey and link to the non existent wiki page.
            if (!property_exists($link_data, "zotero_id")) {
                $output = "[[";
                $output .= $cite_key;
                $output .= "|";
                $output .= $cite_key;
                $output .= "]]";

                $output_strings[$cite_key_idx] = $output;
                $cite_key_idx++;
                continue;
            }
            $output = "[https://www.zotero.org/groups/" . $wgWikiCiteZoteroGroup . "/items/itemKey/";
            $output .= $link_data->{'zotero_id'} . " ";
        }


        if ($cite_style == "b") {
            //Use the built-in style renderer. This is a fallback for when there is no good CSL files

            $data = json_decode(file_get_contents('https://api.zotero.org/groups/' . $wgWikiCiteZoteroGroupID . '/items/' . $link_data->{'zotero_id'}));
    
            if (count($data->{'data'}->{'creators'}) > 2) {
                $author_string = $data->{'data'}->{'creators'}[0]->{'lastName'};
                $author_string .= " Et Al";
            } else if (count($data->{'data'}->{'creators'}) > 1) {
                $author_string = $data->{'data'}->{'creators'}[0]->{'lastName'} . " and " . $data->{'data'}->{'creators'}[1]->{'lastName'};
            } else {
                $author_string = $data->{'data'}->{'creators'}[0]->{'lastName'};
            }
        
            $date = date_parse($data->{'data'}->{'date'});
            if (($date["year"] == NULL)) {
                $date = date_parse_from_format("n Y", $data->{'data'}->{'date'});
                if (($date["year"] == NULL)) {
                    $date = date_parse_from_format("Y", $data->{'data'}->{'date'});
                }
            
            }
        
            if (($cite_format == "p") || ($cite_format = "n")) {
                $output .= $author_string . ", " . $date["year"] . "]";
            } else if ($cite_format = "t") {
                $output .= " ". $author_string . " (" . $date["year"] .")]"; 
            }
        } else {
            $data = json_decode(file_get_contents('https://api.zotero.org/groups/' . $wgWikiCiteZoteroGroupID  . '/items/' . $link_data->{'zotero_id'} . '?format=csljson')); 
            //Zotero returns the data in a format that the csl parser doesn't seem to handle
            if (!property_exists($data->items[0]->issued, "date-parts") && property_exists($data->items[0]->issued, "raw") ) {
                if (is_numeric($data->items[0]->issued->raw)) {
                    $data->items[0]->issued->{'date-parts'}[0][0] = $data->items[0]->issued->raw;
                } else {
                    $data->items[0]->issued->{'date-parts'}[0][0] = date_parse($data->items[0]->issued->raw)["year"];
                    $data->items[0]->issued->{'date-parts'}[0][1] = date_parse($data->items[0]->issued->raw)["month"];
                }
            };
        
            $cite_style = preg_replace("([^a-zA-Z-])", '', $cite_style); 
            $cite_style_format = preg_replace("([^a-zA-Z-])", '', $cite_format);
            if ($cite_style_format == "p") {
                $csl = file_get_contents(__DIR__ . '/csl/' . $cite_style . '.csl'); 
            } else {
                $csl = file_get_contents(__DIR__ . '/csl/' . $cite_style . '-' . $cite_style_format . '.csl'); 
            }
            $citeproc = new citeproc($csl);
            $tmp =  $citeproc->render($data->items[0], "citation");
            if ($num_cite_keys > 1) {
                 if (($tmp[0] == "(") && ($tmp[strlen($tmp) - 1] == ")")) {
                    $output .= substr($tmp, 1, strlen($tmp) - 2);
                 }
            } else {
                $output .= $tmp;
            }
            $output .= "]";
        }
        if ( $title->exists() ) {
            $output .= "]";
            
        }
        $output_strings[$cite_key_idx] = $output;
        $cite_key_idx++;
    }

    if ((($cite_style == "b" ) && ($cite_format == "p")) || ($num_cite_keys > 1)) {
        $output = "(";
        $cite_key_idx = 0;
        for ($cite_key_idx = 0; $cite_key_idx < $num_cite_keys; $cite_key_idx++) {
            $output .= $output_strings[$cite_key_idx];
            if ($cite_key_idx < ($num_cite_keys - 1)) {
                $output .= "; ";
            }
        }
        $output .= ")";
    }
    
    return $output;
}


function CitePaperRenderParserFunction( $parser, $cite_key = '', $cite_style = 'b', $param3 = '' ) {

    //$parser->disableCache();

    return RenderCite($cite_key, "p", $cite_style);

}

function CitetPaperRenderParserFunction( $parser, $cite_key = '', $cite_style = 'b') {

    //$parser->disableCache();

    return RenderCite($cite_key, "t", $cite_style);

}
 
// Render the output of the parser function.
function CitePaperInfoboxRenderParserFunction( $parser ) {
    global $wgWikiCiteLinkerURL;
    global $wgWikiCiteZoteroGroupID;

    $link_data = json_decode(file_get_contents($wgWikiCiteLinkerURL . 'wikicite_api.php?wiki_id=' . $parser->getTitle()));
    $data = json_decode(file_get_contents('https://api.zotero.org/groups/' . $wgWikiCiteZoteroGroupID . '/items/' . $link_data->{'zotero_id'}));
    

    //$parser->disableCache();
    // The input parameters are wikitext with templates expanded.
    // The output should be wikitext too.
    $output = "{{#ifexist:File:{{PAGENAME}}.pdf|{{WikiPapersPDFBox|{{filepath:{{PAGENAME}}.pdf}} {{PAGENAME}}.pdf}}}}";
    if (property_exists($data->{'data'},'abstractNote') && (strlen($data->{'data'}->{'abstractNote'}) > 0))
        $output .= "{{Collapse|Abstract| " . $data->{'data'}->{'abstractNote'} ." |}}\n";
    $output .= "{| class=\"collapsible\" width=\"100%\" style=\"width: 30em; font-size: 90%; border: 1px solid #aaaaaa; background-color: #f9f9f9; color: black; margin-bottom: 0.5em; margin-left: 1em; padding: 0.2em; float: right; clear: right; text-align:left;list-style-type: none;\"\n";
    $output .= "! style=\"text-align: center; background-color:#ccccff;\" colspan=\"2\" |<big>{{PAGENAME}}</big>\n";
    $output .= "|-\n";
    $output .= "|* [" . $wgWikiCiteLinkerURL . "link.php?wiki_id={{PAGENAME}} WikiCite / Zotero Entry] \n";
    //$output .= "* '''Title:''' " . var_dump($data->{'data'}) . "\n";
    if (property_exists($data->{'data'},'title') && (strlen($data->{'data'}->{'title'}) > 0))
        $output .= "* '''Title:''' " . $data->{'data'}->{'title'} . "\n";
    
    $output .= "* '''Author(s):''' ";
    $first = True;
    foreach($data->{'data'}->{'creators'} as $author) {
        if (! $first)
            $output .= " and ";
        $first = False;
        if (!property_exists($author, "lastName") || !property_exists($author, "firstName")) {
            if (property_exists($author, "name")) {
                $output .= $author->{'name'} . " " ;
            } else {
                $output .= "Unknown author ";
            }
        } else {
            $output .= $author->{'lastName'} . ", " . $author->{'firstName'} . " " ;
        }
    }
    $output .= "\n";
    if (property_exists($data->{'data'},'publicationTitle') && (strlen($data->{'data'}->{'publicationTitle'}) > 0))
        $output .= "* '''Journal:''' " . $data->{'data'}->{'publicationTitle'} . "\n";
    if (property_exists($data->{'data'},'date') && (strlen($data->{'data'}->{'date'}) > 0))
        $output .= "* '''Date:''' " . $data->{'data'}->{'date'} . "\n";
    if (property_exists($data->{'data'},'volume') && (strlen($data->{'data'}->{'volume'}) > 0))
        $output .= "* '''Volume:''' " . $data->{'data'}->{'volume'} . "\n";
    if (property_exists($data->{'data'},'issue') && (strlen($data->{'data'}->{'issue'}) > 0))
        $output .= "* '''Issue:''' " . $data->{'data'}->{'issue'} . "\n";
    if (property_exists($data->{'data'},'pages') && (strlen($data->{'data'}->{'pages'}) > 0))
        $output .= "* '''Pages:''' " . $data->{'data'}->{'pages'} . "\n";
    if (property_exists($data->{'data'},'DOI') && (strlen($data->{'data'}->{'DOI'}) > 0))
        $output .= "* '''DOI:''' " . $data->{'data'}->{'DOI'} . "\n";
    if (property_exists($data->{'data'},'ISSN') && (strlen($data->{'data'}->{'ISSN'}) > 0))
        $output .= "* '''ISSN:''' " . $data->{'data'}->{'ISSN'} . "\n";
    if (property_exists($data->{'data'},'url') && (strlen($data->{'data'}->{'url'}) > 0))
        $output .= "* '''URL:''' [" . $data->{'data'}->{'url'} . "]\n";
    
    $output .= "|}";
    
    $output .= "[[Category:Papers]]";
 
    return array( $output, 'noparse' => false );
    return $output;
}


// Render the output of the parser function.
function CiteReferenceRenderParserFunction( $parser, $ref_key, $ref_style = 'b') {
    global $wgWikiCiteLinkerURL;
    global $wgWikiCiteZoteroGroupID;

    $link_data = json_decode(file_get_contents($wgWikiCiteLinkerURL . '/wikicite_api.php?wiki_id=' . $ref_key));
    
    //$parser->disableCache();
    // The input parameters are wikitext with templates expanded.
    // The output should be wikitext too.
    //

    $output = "*  ";
    if ($ref_style == "b") {
        $data = json_decode(file_get_contents('https://api.zotero.org/groups/' . $wgWikiCiteZoteroGroupID  . '/items/' . $link_data->{'zotero_id'}));
        $first = True;
        foreach($data->{'data'}->{'creators'} as $author) {
            if (! $first)
                $output .= ", ";
            $first = False;
            if (!property_exists($author, "lastName") || !property_exists($author, "firstName")) {
                if (property_exists($author, "name")) {
                    $output .= $author->{'name'} . " " ;
                } else {
                    $output .= "Unknown author ";
                }
            } else {
                $output .= $author->{'lastName'} . ", " . $author->{'firstName'} . " " ;
            }
        }
        $output .= " (";
        $output .= $data->{'data'}->{'date'};
        $output .= "). ";
        $output .= $data->{'data'}->{'title'};
        $output .= "\n";
    } else {
        if (!property_exists( $link_data, 'zotero_id')) {
            $output .=  $ref_key . " could not be found";
        } else {
            $data = json_decode(file_get_contents('https://api.zotero.org/groups/' . $wgWikiCiteZoteroGroupID  . '/items/' . $link_data->{'zotero_id'} . '?format=csljson'));
            if (!property_exists($data->items[0]->issued, "date-parts") && property_exists($data->items[0]->issued, "raw") ) {
                if (is_numeric($data->items[0]->issued->raw)) {
                    $data->items[0]->issued->{'date-parts'}[0][0] = $data->items[0]->issued->raw;
                } else {
                    $data->items[0]->issued->{'date-parts'}[0][0] = date_parse($data->items[0]->issued->raw)["year"];
                    $data->items[0]->issued->{'date-parts'}[0][1] = date_parse($data->items[0]->issued->raw)["month"];
                }
            };
            $ref_style = preg_replace("([^a-zA-Z-])", '', $ref_style);
            $csl = file_get_contents(__DIR__ . '/csl/'. $ref_style . '.csl');
            $citeproc = new citeproc($csl);
            $output .=  $citeproc->render($data->items[0], "bibliography");
        }
    }

 
    return array( $output, 'noparse' => false );
    //    return $output;
}

//Insert an auto-generated bibliography section into the wiki page from the {{cite}} templates in the page
function CiteBibliographyRenderParserFunction ( $parser ) {

    //$parser->disableCache();
    
    $output = "\n== Bibliography ==\n";


    //Get the full text of the page to manually try and find any {{cite}} entries
    $page = WikiPage::factory ( $parser->getTitle() );
    $source = $page->getText( Revision::RAW );

    $source_tmp = $source;
    $total_cite_keys = array();
    
    //Go through the text and find {{cite entries.
    while (strlen($source_tmp) > 0) {

        //Either search for a template, or the actual parser function
        $pos1 = strpos( $source_tmp, "{{cite" );
        $pos2 = strpos( $source_tmp, "{{#cite: " );

        if (($pos1 === false) && ($pos2 === false)) {
            break;
        }
        if (($pos1 !== false) && ($pos2 !== false)) {
            $process_pos = min($pos1, $pos2);
        } else if ($pos1 !== false) {
            $process_pos = $pos1;
        } else {
            $process_pos = $pos2;
        }

        $source_tmp = substr($source_tmp, $process_pos);
        $pos_close = strpos( $source_tmp, "}}"); 
        $my_reference = substr($source_tmp, 0, $pos_close + 2);        

        $source_tmp = substr($source_tmp, $pos_close + 2);

        //Make sure we don't create circular parsing references.
        if (strpos($my_reference, "citebibliography") !== false) continue;
        if (strpos($my_reference, "cite_ref") !== false) continue;
        if (strpos($my_reference, "cite_page") !== false) continue;
        
        $pos_start = strpos ($my_reference, "|");
        if ($pos_start === false) {
            $pos_start = strpos($my_reference, ": ");
        }
        $cite_key = substr( $my_reference, $pos_start + 1);
        $pos_end = strpos ( $cite_key, "|");
        if ($pos_end === false) {
            $pos_end = strpos ( $cite_key, "}}");
        }
        $cite_keys = substr ($cite_key, 0, $pos_end);
        $cite_keys = explode (",", $cite_keys);
        foreach ($cite_keys as $cite_key) {
            array_push ( $total_cite_keys, $cite_key);
        }


    }

    $total_cite_keys = array_unique($total_cite_keys);

    foreach ($total_cite_keys as $cite_key) {
        $output .= "{{#citeref: " . $cite_key . "|" . $cite_style . "}}\n";
    }
    
    return array ( $output , 'noparse' => false);
}
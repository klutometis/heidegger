#!/usr/bin/env python3

import re
from preprocess import remove_footnotes, rejoin_split_text

def test_case():
    # Your exact example
    test_text = """Die transzendentale »Allgemeinheit« des Phänomens der Sorge 
und aller fundamentalen Existenzialien hat andererseits jene 
Weite, durch 


1 a. a. O. S. 49. Schon in der Stoa war irepipva ein fester Terminus und kehrt im N. T. wieder, in der Vulgata als sollicitudo. - Die in der vorstehenden existenzialen Analytik des Daseins befolgte Blickrichtung auf die »Sorge« erwuchs dem Verf. im Zusammenhang der Versuche einer Interpretation der augustinischen - das heißt griechisch-christlichen - Anthropologie mit Rücksicht auf die grundsätzlichen Fundamente, die in der Ontologie des Aristoteles erreicht wurden. 



200 


die der Boden vorgegeben wird, auf dem sich jede ontisch-welt- 
anschauliche Daseinsauslegung bewegt, mag sie das Dasein als 
»Lebenssorge« und Not oder gegenteilig verstehen."""

    print("=== ORIGINAL ===")
    print(repr(test_text))
    print("\n" + test_text)
    
    print("\n=== STEP 1: REMOVE FOOTNOTES ===")
    after_footnotes = remove_footnotes(test_text)
    print(repr(after_footnotes))
    print("\n" + after_footnotes)
    
    print("\n=== STEP 2: REJOIN SPLIT TEXT ===") 
    after_rejoin = rejoin_split_text(after_footnotes)
    print(repr(after_rejoin))
    print("\n" + after_rejoin)
    
    print("\n=== EXPECTED RESULT ===")
    expected = """Die transzendentale »Allgemeinheit« des Phänomens der Sorge 
und aller fundamentalen Existenzialien hat andererseits jene 
Weite, durch die der Boden vorgegeben wird, auf dem sich jede ontisch-welt- 
anschauliche Daseinsauslegung bewegt, mag sie das Dasein als 
»Lebenssorge« und Not oder gegenteilig verstehen."""
    print(expected)
    
if __name__ == "__main__":
    test_case()

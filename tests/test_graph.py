from complaints_pipeline.graph import encode_graph_path

def test_encode_graph_path():
    assert encode_graph_path("Backups/Complaints", "a b.csv").endswith("a%20b.csv")

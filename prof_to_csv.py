import pstats
import csv

# Load the .prof file
p = pstats.Stats('output.prof')

# Open a CSV file to save the results
with open('profiling_results.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    
    # Write header row
    writer.writerow(['ncalls', 'tottime', 'percall', 'cumtime', 'percall_cum', 'filename:lineno(function)'])
    
    # Sort by cumulative time and process each entry
    p.strip_dirs().sort_stats('cumulative')
    
    # Iterate over the stats and write each row
    for key, func in p.stats.items():  # Iterate over the stats dictionary
        ncalls = func[0]  # Number of calls
        tottime = func[1]  # Total time
        percall = tottime / ncalls if ncalls else 0  # Time per call
        cumtime = func[2]  # Cumulative time
        percall_cum = cumtime / ncalls if ncalls else 0  # Cumulative time per call
        filename_lineno_function = f'{key[0]}:{key[1]}({key[2]})'  # Filename:line(function)
        
        # Write the row to CSV
        writer.writerow([ncalls, tottime, percall, cumtime, percall_cum, filename_lineno_function])

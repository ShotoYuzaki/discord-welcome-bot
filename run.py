import os
from keep_alive import keep_alive
from main import main

if __name__ == "__main__":
    # Start the web server for uptime monitoring
    keep_alive()
    
    # Start the Discord bot
    main()

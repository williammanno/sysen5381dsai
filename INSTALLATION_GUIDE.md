# R Package Installation Guide

## Problem
Installing `usethis`, `gert`, and `credentials` packages in R is failing.

## Common Issues and Solutions

### 1. **gert Package - System Dependencies (Most Common on macOS)**

The `gert` package requires `libgit2` to be installed on your system. On macOS, this is often the main issue.

#### Solution for macOS:
```bash
# Install libgit2 using Homebrew
brew install libgit2
```

Then try installing the packages again in R:
```r
install.packages(c("usethis", "gert", "credentials"))
```

### 2. **Alternative: Install gert from Source**

If the binary package fails, try installing from source:
```r
install.packages("gert", type = "source")
```

### 3. **Check CRAN Mirror**

Sometimes the default CRAN mirror is slow or unavailable. Try:
```r
# Set a reliable CRAN mirror
options(repos = c(CRAN = "https://cran.rstudio.com/"))

# Then install
install.packages(c("usethis", "gert", "credentials"))
```

### 4. **Install Packages Individually**

If installing all at once fails, try one at a time to see which one is causing issues:
```r
install.packages("usethis")
install.packages("gert")
install.packages("credentials")
```

### 5. **Install Dependencies First**

Some packages have many dependencies. Install with dependencies explicitly:
```r
install.packages(c("usethis", "gert", "credentials"), dependencies = TRUE)
```

### 6. **Check R Version**

Make sure you're using a recent version of R. These packages may require R >= 4.0:
```r
R.version.string
```

### 7. **Use the Diagnostic Script**

Run the provided `install_packages.R` script to diagnose the issue:
```r
source("install_packages.R")
```

## Quick Fix (macOS)

If you're on macOS and getting errors with `gert`, run these commands in Terminal:

```bash
# Install system dependency
brew install libgit2

# Then in R or RStudio
install.packages(c("usethis", "gert", "credentials"))
```

## Still Having Issues?

1. **Check the error message** - What specific error are you seeing?
2. **Check R version** - Run `R.version` in R
3. **Check if Homebrew is installed** - Run `brew --version` in Terminal
4. **Try installing from GitHub** (for gert):
   ```r
   if (!requireNamespace("remotes", quietly = TRUE)) {
     install.packages("remotes")
   }
   remotes::install_github("r-lib/gert")
   ```

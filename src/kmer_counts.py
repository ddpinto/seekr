#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Description
-----------
Generates a kmer count matrix of m rows by n columns,
where m is the number of transcripts in a fasta file and n is 4^kmer.

Examples
--------
The default settings produce a binary, normalized numpy file:
    $ python kmer_counts.py /path/to/rnas.fa -o /path/to/out.npy

To get a human readable csv file, set the nonbinary flag:
    $ python kmer_counts.py /path/to/rnas.fa -o /path/to/out.csv -nb

If you want to add default labels, also set the label flag:
    $ python kmer_counts.py /path/to/rnas.fa -o /path/to/out.csv -nb -lb

You can change also change the size of the kmer you're using, and prevent normalization:
    $ python kmer_counts.py /path/to/rnas.fa -o /path/to/out.npy -k 4 -nc -ns

Notes
-----
For more sophisticated options, you cannot use the command-line, but need python instead.
To label the axes of the matrix, for example, you can call BasicCounter('/path/rnas.fa').to_csv(names)

Issues
------
Any issues can be reported to https://github.com/CalabreseLab #TODO

---
"""

import sys
import argparse
import numpy as np

from collections import defaultdict
from itertools import product
from pandas import DataFrame

from my_tqdm import my_tqdm
from fasta_reader import Reader

class BasicCounter:
    """Generates overlapping kmer counts for a fasta file

    Parameters
    ----------
    infasta : str (default=None)
        Full path to fasta file to be counted
    outfile : str (default=None)
        Full path to the counts file to be saved
    k : int (default=6)
        Size of kmer to be counted
    binary : bool (default=True)
        Saves as numpy array if True, else saves as csv
    mean : bool, np.array, str (default=True)
        Set the mean to 0 for each kmer/column of the count matrix.
        If str, provide path to a previously calculated mean array.
    std : bool or str (default=True)
        Set the std. dev. to 1 for each kmer/column of the count matrix
        If str, provide path to a previously calculated std array.
    leave : bool (default=True)
        Set to False if get_counts is used within another tqdm loop
    silent : bool (default=False)
        Set to True to turn off tqdm progress bar

    Attributes
    ----------
    counts : None
        Stores the ndarray of kmer counts
    kmers : list
        str elements of all kmers of size k
    map : dict
        Mapping of kmers to column values
    """
    def __init__(self, infasta=None, outfile=None, k=6,
                 binary=True, mean=True, std=True,
                 leave=True, silent=False, label=False):
        self.infasta = infasta
        self.seqs = None
        if infasta is not None:
            self.seqs = Reader(infasta).get_seqs()
        self.outfile = outfile
        self.k = k
        self.binary = binary
        self.mean = mean
        if isinstance(mean, str):
            self.mean = np.load(mean)
        self.std = std
        if isinstance(std, str):
            self.std = np.load(std)
        self.leave = leave
        self.silent = silent
        self.label = label

        self.counts = None
        self.kmers = [''.join(i) for i in product('AGTC', repeat=k)]
        self.map = {k:i for k,i in zip(self.kmers, range(4**k))}

        if len(self.seqs) == 1 and self.std is True:
            err = ('You cannot standardize a single sequence. '
                   'Please pass the path to an std. dev. array, '
                   'or use raw counts by setting std=False.')
            raise ValueError(err)

    def occurrences(self, row, seq):
        """Counts kmers on a per kilobase scale"""
        counts = defaultdict(int)
        length = len(seq)
        increment = 1000/length
        for c in range(length-self.k+1):
            kmer = seq[c:c+self.k]
            counts[kmer] += increment
        for kmer, n in counts.items():
            if kmer in self.map:
                row[self.map[kmer]] = n
        return row

    def _progress(self):
        """Determine which iterator to loop over for counting."""
        if self.silent:
            return self.seqs

        if not self.leave:
            tqdm_seqs = my_tqdm()(self.seqs, desc='Kmers', leave=False)
        else:
            tqdm_seqs = my_tqdm()(self.seqs)

        return tqdm_seqs

    def center(self):
        """mean center counts by column"""
        if self.mean is True:
            self.mean  = np.mean(self.counts, axis=0)
        self.counts -= self.mean

    def standardize(self):
        """divide out the standard deviations from columns of the count matrix"""
        if self.std is True:
            self.std = np.std(self.counts, axis=0)
        self.counts /= self.std

    def get_counts(self):
        """Generates kmer counts for a fasta file"""
        self.counts = np.zeros([len(self.seqs), 4**self.k], dtype=np.float32)
        seqs = self._progress()
        for i, seq in enumerate(seqs):
            self.counts[i] = self.occurrences(self.counts[i], seq)
        if self.mean is not False:
            self.center()
        if self.std is not False:
            self.standardize()

    def save(self, names=None):
        """Saves the counts appropriately based on current settings.

        There are four output methods for the counts:
        1. Binary. This saves just the counts as a binary numpy array.
        2. No labels. Saves in plain text, but without any labels.
        3. Default names. If no names are provided, fasta headers will be used as labels.
        4. Custom names. Provide a list of names if you want to label lncRNAs with your own names.

        Parameters
        ----------
        names : [str] (default=None)
            Unique names for rows of the Dataframe.
        """
        assert not (self.binary and self.label), 'You cannot label a binary file. Set only one as True.'
        assert self.outfile is not None, 'Please provide an outfile location.'
        if self.binary:
            np.save(self.outfile, self.counts)
        elif self.label:
            if names is None:
                names = Reader(self.infasta).get_headers()
            df = DataFrame(data=self.counts, index=names, columns=self.kmers)
            df.to_csv(self.outfile)
        else:
            np.savetxt(self.outfile, self.counts, delimiter=',', fmt='%1.6f')

    def make_count_file(self, names=None):
        """Wrapper function for the most common way to generate count files.
        Given a numpy file name, it will save a numpy file where counts have been:
        cast as a dense array, centered, and standardized.

        Parameters
        ----------
        names : [str] (default=None)
            lncRNA names to pass to self.save
        """
        self.get_counts()
        if self.outfile is not None:
            self.save(names)
        return self.counts

if __name__ == '__main__':
    assert sys.version_info[0] == 3, 'Python version must be 3.x'
    parser = argparse.ArgumentParser(usage=__doc__,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('fasta', help='full path of fasta file')
    parser.add_argument('-o', '--outfile', default='counts.seekr', help='name of file to save counts to')
    parser.add_argument('-k', '--kmer', default=6, help='length of kmers you want to count')
    parser.add_argument('-nb', '--nonbinary', action='store_false', help='select if output should be a csv file')
    parser.add_argument('-uc', '--uncentered', action='store_false', help='select if output should not have the mean subtracted')
    parser.add_argument('-us', '--unstandardized', action='store_false', help='select if output should not be divided by the standard deviation')
    parser.add_argument('-lb', '--label', action='store_true', help='select to save with fasta header labels.')
    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(0)
    args = parser.parse_args()
    counter = BasicCounter(args.fasta, args.outfile, int(args.kmer),
                           args.nonbinary, args.uncentered,
                           args.unstandardized, label=args.label)
    counter.make_count_file()

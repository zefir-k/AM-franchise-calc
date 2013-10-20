#!/usr/bin/env python

###########################################################################################
# This script calculates AM franchise payments.
#
# It uses the bitcoin-python library as interface to
# a locally run bitcoind to retrieve block information.
#
# If BTC/USD exchange rate is not given, weighted prices
# are fetched from bitcoincharts.com and the geometrical
# average of 30d, 7d and 24h is used.
#
# formula: b = (x - e*t/y) * p
# b = franchise payment per GHps
# x = mining income 100%PPS per GHps over mining time t
# e = expenses factor: here 4.17*10^(-7) reflecting $0.15/kWh and 100W/blade
# t = mining time in seconds
# y = exchange rate BTC/USD
# p = PPS rate, 80% for now
#
#
# Command line parameters:
#	-p <pps-rate> -c <diff-cycle> -g <GHps> -e <expenses factor> -y <btcusd-rate>
#	defaults:	p=80
#			c=last completed cycle
#			g=10
#			e=4.170000e-07
#			y=fetched from bitcoincharts
#
# Example: ./am-franchise-calc.py
# Returns: franchise payment for one blade for the past comple difficulty cycle
#          considering expenses calculated from current average BTCUSD exchange rate
#
# Example 2: ./am-franchise-calc.py -g 2350 -y 135.42 -c 130
# Returns: franchise payment for operating 235 blades over difficulty cycle 130
#          considering expenses after an agreed exchange rate of 135.42 USD/BTC
#
# Note: to be able to calculate past franchise payments, you need to preserve
#       values for {g, c, y}, and also constants {e, p} as soon as they change
###########################################################################################

import sys
# if not in syspath, your path to bitcoin-python here
sys.path.append('../bitcoin-python/src')
import bitcoinrpc
import json
import decimal
import urllib2

class PpsCalculator:
	def __init__(self, pps_rate, gh, y, btcusd = 0):
		self.pps_rate = pps_rate
		self.gh = gh
		self.conn = bitcoinrpc.connect_to_local()
		self.blockcount = self.conn.getblockcount()
		self.lastblock = self.getblock(self.blockcount)
		self.y = y
		self.btcusd = btcusd
		if btcusd <= 0: self.btcusd = self.get_btcusd()
		

	def get_btcusd(self):
		d = json.load(urllib2.urlopen("http://api.bitcoincharts.com/v1/weighted_prices.json"))
		r30d = float(d["USD"]["30d"])
		r7d = float(d["USD"]["7d"])
		r24h = float(d["USD"]["24h"])
		print r30d, r7d, r24h
		return (r30d * r7d * r24h)**(1/3.0)

	def btc_per_second_at_diff(self, diff):
		DIFF1 = 2**32; GHPS = 1e9; BLOCK_REWARD = 25
		return GHPS * BLOCK_REWARD / float(DIFF1 * diff)

	def getblock(self, block_nr):
		if block_nr > self.blockcount:
			return self.lastblock
		blockhash = self.conn.getblockhash(block_nr)
		return self.conn.getblock(blockhash)

	def get_franchise_payment(self, period):
		if period == -1: period = (self.blockcount / 2016) -1
		block0 = period * 2016
		block1 = block0 + 2016
		b0 = self.getblock(block0)
		b1 = self.getblock(block1)
		diff = b0['difficulty']
		print "Difficulty period %d (%d-%d) @ difficulty=%d" % (period, block0, block1, diff)
		t0 = b0['time']
		t1 = b1['time']
		dtime = t1 - t0
		print "Duration %d seconds (from %d to %d)" % (dtime, t0, t1)
		bpgs = self.btc_per_second_at_diff(diff)
		gross_pps100 = bpgs * dtime
		my_pps = self.pps_rate / 100.0
		expenses_usd = dtime * self.y
		expenses_btc = expenses_usd / self.btcusd
		net_pps100 = gross_pps100 - expenses_btc
		print "Gross mining income 100PPS per GH:\t%.8f" % (gross_pps100)
		print "Expenses at y=%.2e in USD per GH:\t%.8f" % (self.y, expenses_usd)
		print "Exchange rate USD/BTC:\t%.3f" % self.btcusd
		print "Expenses in BTC per GH:\t\t\t%.8f" % (expenses_btc)
		print "Net earnings 100PPS per GH:\t\t%.8f" % (net_pps100)
		print "Franchise earnings %3dPPS per GH:\t%.8f" % (self.pps_rate, my_pps * net_pps100)
		print "Franchise payment for %d GH:\t\t%.4f" % (self.gh, my_pps * net_pps100 * self.gh)



if __name__ == "__main__":
	import getopt

	# defaults: last cycle, 80%PPS, 0.15USD/kWh, 10 GHps/blade, fetch BTCUSD
	diff_cycle = -1
	pps_rate = 80
	e = 4.17e-7
	ghps = 10
	y = 0

	def usage():
		print "Usage:\t" + sys.argv[0] + "\t-p <pps-rate> -c <diff-cycle> -g <GHps> -e <expenses factor> -y <btcusd-rate>"
		print "\tdefaults:\tp=%d" % pps_rate
		print "\t\t\tc=last completed cycle"
		print "\t\t\tg=%d" % ghps
		print "\t\t\te=%e" % e
		print "\t\t\ty=fetched from bitcoincharts"
		sys.exit(2)

	try:
		opts, args = getopt.getopt(sys.argv[1:],"hp:c:g:e:y:")
	except getopt.GetoptError: usage()
	for opt, arg in opts:
		if opt == '-h': usage()
		elif opt in ("-p"): pps_rate = float(arg)
		elif opt in ("-c"): diff_cycle = int(arg)
		elif opt in ("-g"): ghps = float(arg)
		elif opt in ("-e"): e = float(arg)
		elif opt in ("-y"): y = float(arg)

	PC = PpsCalculator(pps_rate, ghps, e, y)
	PC.get_franchise_payment(diff_cycle)



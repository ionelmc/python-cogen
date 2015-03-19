_These are old (made against cogen 0.1.8)_

Although not the most relevant thing here are some figures for a synthetic helloworld benchmark:

`ab -n 10000 -c 60 `
and
`ab -n 20000 -c 600 `

|Server Software       |Requests per second|Transfer rate|Document Length|Concurrency|
|:---------------------|:------------------|:------------|:--------------|:----------|
|`cogen/0.1.8`           |1290.32            |178.84       |19 bytes       |60         |
|`Twisted/8.0.1` (web2)  |703.30             |155.22       |19 bytes       |60         |
|`TwistedWeb/8.0.1`      |790.12             |112.59       |19 bytes       |60         |
|`cogen/0.1.8`           |1208.40            |170.87       |19 bytes       |600        |
|`Twisted/8.0.1` (web2)  |543.47             |119.94       |19 bytes       |600        |
|`TwistedWeb/8.0.1`      |1315.25            |191.24       |19 bytes       |600        |

All servers have the same document length, the example files for the servers can be found in [here](http://code.google.com/p/cogen/source/browse/trunk/examples/).

Well, not exactly made in the ideal conditions - i wouldn't call a virtual machine ideal but you get the hang of it.
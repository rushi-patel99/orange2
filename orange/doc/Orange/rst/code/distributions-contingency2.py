import Orange
import distributions

table = Orange.data.Table("monks-1.tab")
cont = distributions.Contingency(table.domain["e"], table.domain.classVar)
for ins in table:
    cont [ins["e"]] [ins.getclass()] += 1

print "Contingency items:"

for val, dist in cont.items():
    print val, dist
print

for ins in table:
    cont.add(ins["e"], ins.getclass()) 
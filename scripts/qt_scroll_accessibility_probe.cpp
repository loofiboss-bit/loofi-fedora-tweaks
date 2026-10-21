#include <QApplication>
#include <QAccessible>
#include <QScrollArea>
#include <QWidget>
#include <iostream>
#include <sys/resource.h>
int main(int argc,char **argv) {
    rlimit limit{0,0}; setrlimit(RLIMIT_CORE,&limit);
    QApplication app(argc,argv);
    QScrollArea scroll;
    QWidget *content = new QWidget;
    content->setMinimumSize(1200,1200);
    scroll.setWidget(content);
    scroll.resize(300,200);
    scroll.show(); app.processEvents();
    QAccessibleInterface *iface=QAccessible::queryAccessibleInterface(&scroll);
    if (!iface) return 2;
    int count=iface->childCount();
    if (count < 2) return 3;
    std::cout << "Qt " << qVersion() << " visible children=" << count << std::endl;
    scroll.hide(); app.processEvents();
    std::cout << "Hidden children=" << iface->childCount() << "; requesting previous index=" << count-1 << std::endl;
    auto *child=iface->child(count-1);
    std::cout << "Returned " << child << std::endl;
    if (child != nullptr) return 4;
    if (iface->child(-1) != nullptr) return 5;
    if (iface->child(iface->childCount()) != nullptr) return 6;
    if (iface->child(0) == nullptr) return 7;
    return 0;
}

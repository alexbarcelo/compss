package constraintsTest;

import integratedtoolkit.types.annotations.Constraints;
import integratedtoolkit.types.annotations.Method;
import integratedtoolkit.types.annotations.MultiConstraints;
import integratedtoolkit.types.annotations.Parameter;
import integratedtoolkit.types.annotations.Service;
import integratedtoolkit.types.annotations.Parameter.Direction;
import integratedtoolkit.types.annotations.Parameter.Type;


public interface ConstraintsTestItf {
	
	@Method(declaringClass = "constraintsTest.Implementation1")
	@Constraints(operatingSystemType = "Linux", processorSpeed = (float)2.3)
	void coreElement0();
	
	
	@Method(declaringClass = {
			"constraintsTest.Implementation1",
			"constraintsTest.Implementation2"})
	@Constraints(processorArchitecture = "amd64", memoryAccessTime = (float)200.0)
	void coreElement1();
	
	
	@Method(declaringClass = {
			"constraintsTest.Implementation1",
			"constraintsTest.Implementation2",
			"constraintsTest.Implementation3"})
	@MultiConstraints({
		@Constraints(hostQueue = "q1", processorCPUCount = 2), 
		@Constraints(hostQueue = "q1", memorySTR = 2),
		@Constraints()})
	void coreElement2();
	
	
	@Method(declaringClass = {
			"constraintsTest.Implementation1",
			"constraintsTest.Implementation2"})
	@Constraints(appSoftware = "Blast")
	@MultiConstraints({
		@Constraints(processorCoreCount = 4), 
		@Constraints(appSoftware = "Java", memoryPhysicalSize = (float)2.0, memoryVirtualSize = (float)4.0)})
	void coreElement3();

	
	@Method(declaringClass = {
			"constraintsTest.Implementation1",
			"constraintsTest.Implementation2"})
	@Constraints(storageElemAccessTime = (float)200.0)
	@MultiConstraints({
		@Constraints(storageElemSize = (float)2.0), 
		@Constraints(storageElemSTR = (float)2.0)})
	void coreElement4();
	
	@Service(name = "HmmerObjects", namespace = "http://hmmerobj.worker", port = "HmmerObjectsPort")
	void coreElement5();
	
	@Method(declaringClass = "constraintsTest.Implementation1")
	@Constraints(operatingSystemType = "Windows7", processorCoreCount = 2, memoryPhysicalSize = (float)1.0)
	void coreElementAR1(
			@Parameter(type = Type.FILE, direction = Direction.OUT) String fileName
	);
	
	@Method(declaringClass = "constraintsTest.Implementation1")
	@Constraints(operatingSystemType = "Windows7", processorCoreCount = 1, memoryPhysicalSize = (float)2.0)
	void coreElementAR2(
			@Parameter(type = Type.FILE, direction = Direction.IN) String fileName
	);
}
